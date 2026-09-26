import { createHash } from "node:crypto";
import { researchBackendUrl } from "./research";

export const referenceReportNames = [
  "external-research.md", "external-comparison.md", "model-improvement.md", "portfolio-next-research.md",
] as const;
export type ReferenceReportName = typeof referenceReportNames[number];
export type ResearchReportTarget =
  | { kind: "history" | "portfolio" | "dividends"; id: string }
  | { kind: "reference"; name: ReferenceReportName };
const hashPattern = /^[a-f0-9]{64}$/;

export function parseResearchReportTarget(parts: readonly string[]): ResearchReportTarget | null {
  if (parts.length !== 2) return null;
  const [kind, value] = parts;
  if ((kind === "history" || kind === "portfolio" || kind === "dividends") && hashPattern.test(value)) return { kind, id: value };
  if (kind === "reference") {
    const name = referenceReportNames.find((item) => item === value);
    if (name) return { kind, name };
  }
  return null;
}

export function researchReportHref(target: ResearchReportTarget): string {
  return `/research/reports/${target.kind}/${target.kind === "reference" ? target.name : target.id}`;
}

export function researchReportApiPath(target: ResearchReportTarget): string {
  switch (target.kind) {
    case "history": return `/api/research/history/artifacts/${target.id}`;
    case "portfolio": return `/api/research/portfolio/runs/${target.id}/artifacts/report.md`;
    case "dividends": return `/api/research/portfolio/dividends/runs/${target.id}/artifacts/report.md`;
    case "reference": return `/api/research/reports/${target.name}`;
  }
}

export function legacyResearchReportTarget(pathname: string): ResearchReportTarget | null {
  const patterns: ReadonlyArray<[RegExp, ResearchReportTarget["kind"]]> = [
    [/^\/research\/history\/download\/([a-f0-9]{64})$/, "history"],
    [/^\/api\/research\/history\/artifacts\/([a-f0-9]{64})$/, "history"],
    [/^\/research\/portfolio\/download\/([a-f0-9]{64})\/report\.md$/, "portfolio"],
    [/^\/api\/research\/portfolio\/runs\/([a-f0-9]{64})\/artifacts\/report\.md$/, "portfolio"],
    [/^\/research\/portfolio\/dividends\/download\/([a-f0-9]{64})\/report\.md$/, "dividends"],
    [/^\/api\/research\/portfolio\/dividends\/runs\/([a-f0-9]{64})\/artifacts\/report\.md$/, "dividends"],
    [/^\/research\/portfolio\/download\/reports\/([^/]+)$/, "reference"],
    [/^\/api\/research\/reports\/([^/]+)$/, "reference"],
  ];
  for (const [pattern, kind] of patterns) {
    const match = pattern.exec(pathname);
    if (match) return parseResearchReportTarget([kind, match[1]]);
  }
  return null;
}

export function reportHeadingSlug(text: string): string {
  return text.toLowerCase().trim().replace(/[^\p{L}\p{N}\s_-]/gu, "").replace(/\s+/g, "-") || "section";
}

const localReadingPages = new Set([
  "/research", "/research/progress", "/research/history", "/research/forward", "/research/portfolio",
  "/research/portfolio/dividends", "/research/market", "/research/lab", "/investor",
]);

/** Only known application reading routes, fragments and explicit web references are active. */
export function safeResearchReportLink(value: string, current: ResearchReportTarget): string | undefined {
  if (/[\u0000-\u001f\u007f\\]/.test(value)) return undefined;
  const url = value.trim();
  if (!url || url.startsWith("//")) return undefined;
  if (url.startsWith("#")) {
    try {
      const fragment = decodeURIComponent(url.slice(1));
      return fragment.startsWith("report-") || fragment.startsWith("user-content-")
        ? `#${fragment}` : `#report-${reportHeadingSlug(fragment)}`;
    } catch { return undefined; }
  }
  const external = /^https?:\/\//i.test(url);
  let parsed: URL;
  try { parsed = new URL(url, "https://report.invalid/"); } catch { return undefined; }
  if (parsed.username || parsed.password) return undefined;
  if (external && parsed.protocol !== "https:" && parsed.protocol !== "http:") return undefined;
  if (!external && (/^[a-z][a-z0-9+.-]*:/i.test(url) || url.includes(".."))) return undefined;
  const fragment = parsed.hash ? safeResearchReportLink(parsed.hash, current) ?? "" : "";
  const legacy = legacyResearchReportTarget(parsed.pathname);
  if (legacy) return `${researchReportHref(legacy)}${fragment}`;
  const canonical = /^\/research\/reports\/([^/]+)\/([^/]+)$/.exec(parsed.pathname);
  if (canonical) {
    const target = parseResearchReportTarget(canonical.slice(1));
    if (target) return `${researchReportHref(target)}${fragment}`;
    return undefined;
  }
  if (external) {
    let decoded: string;
    try { decoded = decodeURIComponent(parsed.href); } catch { return undefined; }
    if (/\.(?:md|markdown)(?:$|[?#&/])/i.test(decoded)) return undefined;
    return parsed.href;
  }
  const relativeName = url.split(/[?#]/, 1)[0].replace(/^\.\//, "");
  const reference = parseResearchReportTarget(["reference", relativeName]);
  if (reference) return `${researchReportHref(reference)}${fragment}`;
  if (/^[a-f0-9]{64}\.md$/.test(relativeName)) return `${researchReportHref({ kind: "history", id: relativeName.slice(0, -3) })}${fragment}`;
  if (relativeName === "report.md" && (current.kind === "portfolio" || current.kind === "dividends")) return `${researchReportHref(current)}${fragment}`;
  if (url.startsWith("/") && localReadingPages.has(parsed.pathname) && !parsed.search) return `${parsed.pathname}${parsed.hash}`;
  return undefined;
}

export type ResearchReportResult =
  | { status: "available"; markdown: string; sha256: string }
  | { status: "missing" | "empty" | "unavailable" | "integrity_error" | "invalid_text" };

export async function readResearchReport(target: ResearchReportTarget, fetcher: typeof fetch = fetch): Promise<ResearchReportResult> {
  if (!parseResearchReportTarget([target.kind, target.kind === "reference" ? target.name : target.id])) return { status: "missing" };
  try {
    const response = await fetcher(`${researchBackendUrl()}${researchReportApiPath(target)}`, {
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15000),
    });
    if (response.status === 404) return { status: "missing" };
    if (!response.ok) return { status: "unavailable" };
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length === 0) return { status: "empty" };
    const sha256 = createHash("sha256").update(bytes).digest("hex");
    if (target.kind === "history" && sha256 !== target.id) return { status: "integrity_error" };
    let markdown: string;
    try { markdown = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes); }
    catch { return { status: "invalid_text" }; }
    if (!markdown.trim()) return { status: "empty" };
    return { status: "available", markdown, sha256 };
  } catch { return { status: "unavailable" }; }
}
