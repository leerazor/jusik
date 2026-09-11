import { researchBackendUrl } from "@/lib/research";

export async function GET(_request: Request, context: { params: Promise<{ artifactId: string }> }): Promise<Response> {
  const { artifactId } = await context.params;
  if (!/^[a-f0-9]{64}$/.test(artifactId)) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/history/artifacts/${artifactId}`, { cache: "force-cache", signal: AbortSignal.timeout(15000) });
    if (!response.ok) return new Response("Not found", { status: 404 });
    return new Response(response.body, { headers: { "cache-control": "public, max-age=31536000, immutable", "content-disposition": response.headers.get("content-disposition") ?? "attachment", "content-type": "text/markdown; charset=utf-8", "x-content-type-options": "nosniff" } });
  } catch { return new Response("Research backend unavailable", { status: 502 }); }
}
