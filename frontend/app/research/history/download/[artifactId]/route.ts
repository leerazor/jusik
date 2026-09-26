import { parseResearchReportTarget, researchReportHref } from "@/lib/research-reports";

export async function GET(_request: Request, context: { params: Promise<{ artifactId: string }> }): Promise<Response> {
  const { artifactId } = await context.params;
  const target = parseResearchReportTarget(["history", artifactId]);
  if (!target) return new Response("Not found", { status: 404 });
  return new Response(null, { status: 307, headers: { location: researchReportHref(target), "cache-control": "no-store" } });
}
