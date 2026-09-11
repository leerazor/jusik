import { researchBackendUrl } from "@/lib/research";

const evidenceIdPattern = /^[a-f0-9]{64}$/;

export async function GET(
  _request: Request,
  context: { params: Promise<{ evidenceId: string }> },
): Promise<Response> {
  const { evidenceId } = await context.params;
  if (!evidenceIdPattern.test(evidenceId)) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/actions/evidence/${evidenceId}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
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
