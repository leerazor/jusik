import { researchBackendUrl } from "@/lib/research";

const allowed = new Set(["start", "end"]);

export async function GET(
  _request: Request,
  context: { params: Promise<{ boundary: string }> },
): Promise<Response> {
  const { boundary } = await context.params;
  if (!allowed.has(boundary)) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(
      `${researchBackendUrl()}/api/research/validation/prospective/boundary-captures/${boundary}`,
      { cache: "no-store", signal: AbortSignal.timeout(20000) },
    );
    if (!response.ok) return new Response("Not found", { status: 404 });
    return new Response(response.body, {
      headers: {
        "cache-control": "private, no-store",
        "content-disposition": response.headers.get("content-disposition") ?? "attachment",
        "content-type": "application/octet-stream",
        "x-content-type-options": "nosniff",
        "x-content-sha256": response.headers.get("x-content-sha256") ?? "",
      },
    });
  } catch {
    return new Response("Research backend unavailable", { status: 502 });
  }
}
