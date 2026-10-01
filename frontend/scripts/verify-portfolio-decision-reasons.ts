import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PolicyDecisionReasons } from "../app/research/portfolio/decision-reasons";
import {
  summarizePortfolioDecisionReasons,
  type PortfolioDecisionEvent,
} from "../lib/portfolio-decision-reasons";

const event = (kind: PortfolioDecisionEvent["kind"], detail: string, value: string | null = null): PortfolioDecisionEvent => ({
  at: "2026-09-01T00:00:00Z", kind, detail, value,
});
const repeated = event("band_skip", "<script>alert(1)</script>", "0.01");
const first = [event("frequency_skip", "cadence"), repeated, repeated, event("risk_exit", "exit")];
const second = [event("cap_constraint_deferred", "non-opening holdings"), event("reentry", "ready")];
const summary = summarizePortfolioDecisionReasons(first);
assert.deepEqual(summary.counts, { frequency_skip: 1, band_skip: 2, cap_constraint_deferred: 0 });
assert.equal(summary.events.length, 3);
assert.strictEqual(summary.events[1], repeated);
assert.strictEqual(summary.events[2], repeated);
assert.deepEqual(summarizePortfolioDecisionReasons([]).counts, { frequency_skip: 0, band_skip: 0, cap_constraint_deferred: 0 });
assert.equal(summarizePortfolioDecisionReasons([event("risk_exit", "exit")]).events.length, 0);

const html = renderToStaticMarkup(createElement(PolicyDecisionReasons, { comparisons: [
  { policy: "combined", base: { policy_events: first } },
  { policy: "reentry_only", base: { policy_events: second } },
  { policy: "corrected_control", base: { policy_events: [event("reentry", "ready")] } },
] }));
assert.match(html, /기록된 사유 없음 · 원인 알 수 없음/);
assert.match(html, /원인 알 수 없음/);
assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
assert.doesNotMatch(html, /<script>/);
assert.match(html, /사유 원문 3건/);
assert.match(html, /사유 원문 1건/);
assert.match(html, /사유 원문 0건/);
assert.match(html, /재진입 \+ 변동성<\/td><td>1<\/td><td>2<\/td><td>0<\/td>/);
assert.match(html, /재진입만<\/td><td>0<\/td><td>0<\/td><td>1<\/td>/);
assert.match(html, /<th>at \(UTC\)<\/th><th>kind<\/th><th>detail<\/th><th>value<\/th>/);
assert.doesNotMatch(html, /비용 2배/);
assert.match(renderToStaticMarkup(createElement(PolicyDecisionReasons, { comparisons: [] })), /비교할 정책 기록이 없어 사유를 알 수 없습니다/);
console.log("Portfolio decision reason checks passed: granularity, repetition, policy isolation, empty states and escaped evidence.");
