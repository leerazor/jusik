import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { z } from "zod";
import {
  legacyResearchReportTarget, parseResearchReportTarget, readResearchReport, referenceReportNames,
  researchReportApiPath, researchReportHref, safeResearchReportLink, type ResearchReportTarget,
} from "../lib/research-reports";
import { describeComparisonOutcome, findReportStudy, getComparisonSettings, getStudyNarrative, researchCadenceExplanation, researchSettingLabels, researchSettingName } from "../lib/research-narrative";
import { researchProgressSchema, type Comparison, type Study } from "../lib/research-progress";
import { renderResearchReport } from "../app/research/reports/report-markdown";
import { GET as historyDownload } from "../app/research/history/download/[artifactId]/route";
import { GET as portfolioDownload } from "../app/research/portfolio/download/[...path]/route";
import { GET as dividendDownload } from "../app/research/portfolio/dividends/download/[runId]/[name]/route";

const sample = "# Original\n\n118.93553% · 4,933,874.01원\n";
const digest = createHash("sha256").update(sample).digest("hex");
const history: ResearchReportTarget = { kind: "history", id: digest };
const runId = "b".repeat(64);
const portfolio: ResearchReportTarget = { kind: "portfolio", id: runId };
const dividends: ResearchReportTarget = { kind: "dividends", id: runId };

const successFetch: typeof fetch = async (_input, init) => {
  assert.equal(init?.cache, "no-store");
  assert.equal(init?.redirect, "error");
  return new Response(sample);
};

async function main(): Promise<void> {
  for (const target of [history, portfolio, dividends, ...referenceReportNames.map((name) => ({ kind: "reference" as const, name }))]) {
    assert.deepEqual(parseResearchReportTarget(researchReportHref(target).split("/").slice(3)), target);
    assert.ok(researchReportApiPath(target).startsWith("/api/research/"));
  }
  for (const parts of [[], ["history"], ["history", "../secret"], ["history", "A".repeat(64)], ["portfolio", "x"], ["reference", "unknown.md"], ["reference", "../external-research.md"], ["history", digest, "extra"]]) assert.equal(parseResearchReportTarget(parts), null);
  const read = await readResearchReport(history, successFetch);
  assert.equal(read.status, "available");
  if (read.status === "available") { assert.equal(read.markdown, sample); assert.equal(read.sha256, digest); }
  assert.equal((await readResearchReport(portfolio, successFetch)).status, "available", "run ID must not be treated as a report hash");
  assert.equal((await readResearchReport(history, async () => new Response(`${sample}tampered`))).status, "integrity_error");
  assert.equal((await readResearchReport(history, async () => new Response(""))).status, "empty");
  assert.equal((await readResearchReport(portfolio, async () => new Response("  \n"))).status, "empty");
  assert.equal((await readResearchReport(history, async () => new Response(null, { status: 404 }))).status, "missing");
  assert.equal((await readResearchReport(history, async () => new Response(null, { status: 503 }))).status, "unavailable");
  assert.equal((await readResearchReport(history, async () => { throw new Error("offline"); })).status, "unavailable");
  assert.equal((await readResearchReport(portfolio, async () => new Response(new Uint8Array([0xff])))).status, "invalid_text");
  let calls = 0;
  assert.equal((await readResearchReport({ kind: "portfolio", id: "../invalid" }, async () => { calls++; return new Response(sample); })).status, "missing");
  assert.equal(calls, 0);

  const request = new Request("http://localhost/research");
  for (const [response, target] of [
    [await historyDownload(request, { params: Promise.resolve({ artifactId: digest }) }), history],
    [await portfolioDownload(request, { params: Promise.resolve({ path: [runId, "report.md"] }) }), portfolio],
    [await dividendDownload(request, { params: Promise.resolve({ runId, name: "report.md" }) }), dividends],
  ] as const) {
    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), researchReportHref(target));
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("content-disposition"), null);
  }
  for (const name of referenceReportNames) {
    const response = await portfolioDownload(request, { params: Promise.resolve({ path: ["reports", name] }) });
    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), researchReportHref({ kind: "reference", name }));
  }
  assert.equal((await historyDownload(request, { params: Promise.resolve({ artifactId: "../invalid" }) })).status, 404);
  assert.equal((await portfolioDownload(request, { params: Promise.resolve({ path: [runId, "unsupported.md"] }) })).status, 404);
  assert.equal((await dividendDownload(request, { params: Promise.resolve({ runId: "invalid", name: "report.md" }) })).status, 404);

  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response("column\n1\n", { headers: { "content-type": "text/csv", "content-disposition": "attachment; filename=equity.csv" } });
    for (const response of [await portfolioDownload(request, { params: Promise.resolve({ path: [runId, "equity.csv"] }) }), await dividendDownload(request, { params: Promise.resolve({ runId, name: "equity.csv" }) })]) {
      assert.equal(response.status, 200);
      assert.equal(await response.text(), "column\n1\n");
      assert.ok(response.headers.get("content-disposition")?.startsWith("attachment"));
    }
  } finally { globalThis.fetch = originalFetch; }

  const oldHistory = `/research/history/download/${digest}`;
  assert.deepEqual(legacyResearchReportTarget(oldHistory), history);
  assert.equal(safeResearchReportLink(`${oldHistory}?download=1#Original`, history), `${researchReportHref(history)}#report-original`);
  assert.equal(safeResearchReportLink(`https://old.example/research/portfolio/download/${runId}/report.md`, history), researchReportHref(portfolio));
  assert.equal(safeResearchReportLink("external-research.md?raw=1", history), "/research/reports/reference/external-research.md");
  assert.equal(safeResearchReportLink(`${digest}.md`, history), researchReportHref(history));
  assert.equal(safeResearchReportLink("report.md", portfolio), researchReportHref(portfolio));
  assert.equal(safeResearchReportLink("#Original", history), "#report-original");
  assert.equal(safeResearchReportLink("/research/progress#study-example", history), "/research/progress#study-example");
  assert.equal(safeResearchReportLink("https://example.org/article?q=1#heading", history), "https://example.org/article?q=1#heading");
  for (const unsafe of ["javascript:alert(1)", "java\nscript:alert(1)", "data:text/html,hello", "file:///etc/passwd", "//remote.example/report", "../private.md", "/etc/passwd", "/research/actions", "unknown.md", "https://example.org/raw.md?raw=1#title", "https://example.org/raw%2Emd", "https://example.org/download?file=raw.md", "https://user:pass@example.org/article"]) assert.equal(safeResearchReportLink(unsafe, history), undefined, unsafe);

  const markdown = "# Repeat\n\n## Repeat\n\n## Repeat-2\n\n## **가격** `118.93553`\n\n| Metric | Value |\n| --- | ---: |\n| Return | 118.93553% |\n\n- Item\n\n> Quote\n\n```ts\nconst safe = 1;\n```\n\n<script>alert('xss')</script>\n\n[unsafe](javascript:alert%281%29) [file](file:///etc/passwd) [unsupported](https://example.org/raw.md)\n\n![chart](https://example.org/track.png)\n\n[original](" + oldHistory + ")\n";
  const rendered = renderResearchReport(markdown, history);
  const html = renderToStaticMarkup(rendered.body);
  assert.equal(new Set(rendered.headings.map((heading) => heading.id)).size, 4);
  assert.deepEqual(rendered.headings.map((heading) => heading.id), ["report-repeat", "report-repeat-2", "report-repeat-2-2", "report-가격-11893553"]);
  for (const heading of rendered.headings) assert.ok(html.includes(`id="${heading.id}"`));
  for (const element of ["<table", "<ul", "<blockquote", "<pre", "<code"]) assert.ok(html.includes(element));
  assert.ok(html.includes("118.93553%"));
  assert.ok(html.includes("&lt;script&gt;"), "raw HTML remains inert readable text");
  for (const fragment of ["<script", "<img", 'href="javascript:', 'href="file:', 'href="https://example.org/raw.md"', "dangerouslySetInnerHTML"]) assert.ok(!html.includes(fragment), fragment);
  assert.ok(html.includes(`href="${researchReportHref(history)}"`));
  assert.ok(html.includes('href="https://example.org/track.png"'));

  const footnotes = renderToStaticMarkup(renderResearchReport("First[^1], repeated[^1], second[^2].\n\n[^1]: First note with [unsafe](javascript:alert%281%29).\n[^2]: Second note with [unsupported](https://example.org/raw.md).\n", history).body);
  const footnoteAnchors = [...footnotes.matchAll(/<a\b[^>]*>/g)].map((match) => match[0]);
  const references = footnoteAnchors.filter((anchor) => anchor.includes("data-footnote-ref="));
  const backreferences = footnoteAnchors.filter((anchor) => anchor.includes("data-footnote-backref="));
  assert.equal(references.length, 3, "all GFM footnote references retain their accessibility markers");
  assert.equal(backreferences.length, 3, "repeated footnotes retain each return link");
  const footnoteIds = new Set([...footnotes.matchAll(/ id="([^"]+)"/g)].map((match) => match[1]));
  for (const anchor of [...references, ...backreferences]) {
    const destination = /href="#([^"]+)"/.exec(anchor)?.[1];
    assert.ok(destination && footnoteIds.has(destination), "every forward and return link resolves to a rendered target");
  }
  for (const reference of references) {
    assert.ok(/ id="user-content-fnref-/.test(reference), "footnote reference retains its return target ID");
    const describedBy = /aria-describedby="([^"]+)"/.exec(reference)?.[1];
    assert.ok(describedBy && describedBy.split(" ").every((id) => footnoteIds.has(id)), "footnote reference points to its accessible description");
  }
  for (const backreference of backreferences) assert.ok(backreference.includes('aria-label="본문으로 돌아가기"'), "return link retains its accessible label");
  assert.ok(!footnotes.includes('href="javascript:'));
  assert.ok(!footnotes.includes('href="https://example.org/raw.md"'));
  assert.ok(!footnotes.includes(" node="), "AST objects are not forwarded to DOM elements");

  const metrics = { label: "fixture", net_return_pct: "0", cash_pct: "0", max_drawdown_pct: "0", max_leverage_pct: "0", annual_turnover_pct: "0", total_cost_krw: "0", trade_days: 0 };
  const comparison: Comparison = { id: "fixture-c1", period_start: "2023-01-01", period_end: "2024-01-01", cost_multiplier: 1, drawdown_basis: "all_observer_nav", cash_basis: "utc_day_last_nav", cash_statistic: "mean", baseline: metrics, candidate: metrics };
  const known: Study = { id: "core10-low-cash", title: "Fixture", published_at: "2026-09-13T00:00:00Z", cohort_id: "fixture", universe_symbols: [], source_sha256: "090944bb3f224e5dd1ff857a9376707fc8049ff24df945a3428208969ac81342", result_sha256: "71c1e5efac632d6f934d5b411d5f217131d0eb635aae121e90aee0373963e445", report_artifact_sha256: "aceef65a6cf64ac8afddfcc0226827ce3146100651706f2e3cab010008dc70fd", price_only: true, dividends_included: false, taxes_included: false, retrospective_reused_data: true, point_in_time_verified: false, comparisons: [comparison, { ...comparison, id: "fixture-c2" }] };
  const equalOutcome = describeComparisonOutcome(comparison);
  assert.equal((equalOutcome.match(/같았습니다/g) ?? []).length, 4, "zero and equal inputs remain ties");
  const oppositeOutcome = describeComparisonOutcome({ ...comparison, baseline: { ...metrics, net_return_pct: "-2", max_drawdown_pct: "10", total_cost_krw: "1" }, candidate: { ...metrics, net_return_pct: "-1", max_drawdown_pct: "5", total_cost_krw: "2" } });
  assert.ok(oppositeOutcome.includes("수익률은 높았습니다") && oppositeOutcome.includes("최대 하락 폭은 작았습니다") && oppositeOutcome.includes("거래 비용은 많았습니다"));
  const settings = getComparisonSettings(known, comparison.id);
  assert.ok(settings);
  assert.deepEqual(settings.baselineRules.slice(0, 3), ["전체 돈 중 투자할 수 있는 한도 60%", "연 변동성 목표 10%", "4주(28일)마다 종목별 투자 비중 점검"]);
  assert.deepEqual(settings.candidateRules.slice(0, 4), ["전체 돈 중 투자할 수 있는 한도 95%", "연 변동성 목표 30%", "8주(56일)마다 종목별 투자 비중 점검", "보유 비중 밴드 2%p · 후보 A"]);
  assert.ok(getComparisonSettings(known, "fixture-c2")?.candidateRules.includes("보유 비중 밴드 4%p · 후보 B"));
  assert.equal(getComparisonSettings(known, "unknown-c1"), null);
  for (const key of ["id", "source_sha256", "result_sha256", "report_artifact_sha256"] as const) {
    const mismatch = { ...known, [key]: key === "id" ? "unknown" : "f".repeat(64) };
    assert.equal(getStudyNarrative(mismatch), null);
    assert.equal(getComparisonSettings(mismatch, comparison.id), null);
    assert.equal(researchSettingName(mismatch, "4주 운용"), "4주 운용");
  }
  assert.equal(researchSettingName(known, "4주 운용"), "4주마다 보유 비중 검토");
  assert.ok(!Object.values(researchSettingLabels).join(" ").includes("기존 방식"));
  for (const term of ["28일", "56일", "투자기간", "반드시", "건너뛰고", "그 사이"]) assert.ok(researchCadenceExplanation.includes(term));

  const fixtureDirectory = process.argv[2];
  let originalCount = 0;
  if (fixtureDirectory) {
    const progress = researchProgressSchema.parse(JSON.parse(await readFile(path.join(fixtureDirectory, "progress.json"), "utf8")));
    const cadenceStudy = progress.research.studies.find((study) => study.id === "volatility15-cadence-5270");
    const improvingFold = cadenceStudy?.comparisons.find((item) => item.id.endsWith("fold_5-c1"));
    assert.ok(improvingFold, "preserve the real fold that contradicts the aggregate study conclusion");
    const improvingOutcome = describeComparisonOutcome(improvingFold);
    assert.ok(improvingOutcome.includes("수익률은 높았습니다") && improvingOutcome.includes("최대 하락 폭은 작았습니다"));
    const described = progress.research.studies.find((study) => getStudyNarrative(study));
    assert.ok(described);
    const artifact = described.report_artifact_sha256;
    assert.equal(findReportStudy(progress, artifact)?.id, described.id);
    assert.equal(findReportStudy(null, artifact), null);
    assert.equal(findReportStudy(progress, "0".repeat(64)), null);
    for (const availability of ["invalid", "unavailable"] as const) {
      assert.equal(findReportStudy({ ...progress, research: { ...progress.research, availability } }, artifact), null);
    }
    for (const field of ["id", "source_sha256", "result_sha256", "report_artifact_sha256"] as const) {
      const altered: Study = { ...described, [field]: field === "id" ? "unknown" : "f".repeat(64) };
      assert.equal(findReportStudy({ ...progress, research: { ...progress.research, studies: [altered] } }, artifact), null);
    }
    const schema = z.array(z.object({ path: z.string(), fixture: z.string().regex(/^original-report-\d+\.txt$/), sha256: z.string(), status: z.number(), api_path: z.string() }));
    const records = schema.parse(JSON.parse(await readFile(path.join(fixtureDirectory, "report-fixtures.json"), "utf8")));
    for (const fixture of records.filter((item) => item.status === 200)) {
      const target = legacyResearchReportTarget(fixture.path);
      assert.ok(target);
      const bytes = await readFile(path.join(fixtureDirectory, fixture.fixture));
      assert.equal(createHash("sha256").update(bytes).digest("hex"), fixture.sha256);
      assert.equal(researchReportApiPath(target), fixture.api_path);
      const actual = await readResearchReport(target, async () => new Response(bytes));
      assert.equal(actual.status, "available");
      if (actual.status !== "available") throw new Error("original report unavailable");
      assert.equal(actual.markdown, bytes.toString("utf8"), "original must remain byte-faithful after UTF-8 decoding");
      const full = renderToStaticMarkup(renderResearchReport(actual.markdown, target).body);
      const originalNumbers = [...actual.markdown.matchAll(/\d+\.\d+%/g)].map((match) => match[0]);
      for (const number of originalNumbers) assert.ok(full.includes(number), `missing original numeric text ${number}`);
      originalCount++;
    }
  }
  console.log(`Research report checks passed; original reports verified: ${originalCount}.`);
}

main().catch((error: unknown) => { console.error(error); process.exitCode = 1; });
