import type { PortfolioRun } from "./research";

export type PortfolioDecisionEvent = PortfolioRun["heldout"]["policy_events"][number];
export type PortfolioPolicyComparison = NonNullable<PortfolioRun["policy_experiment"]>["comparisons"][number];
export type DecisionReasonKind = "frequency_skip" | "band_skip" | "cap_constraint_deferred";

export type DecisionReasonSummary = {
  counts: Record<DecisionReasonKind, number>;
  events: PortfolioDecisionEvent[];
};

/** Event counts retain their original granularity; they are not trade or calendar-day counts. */
export function summarizePortfolioDecisionReasons(events: readonly PortfolioDecisionEvent[]): DecisionReasonSummary {
  const summary: DecisionReasonSummary = {
    counts: { frequency_skip: 0, band_skip: 0, cap_constraint_deferred: 0 },
    events: [],
  };
  for (const event of events) {
    if (event.kind === "frequency_skip" || event.kind === "band_skip" || event.kind === "cap_constraint_deferred") {
      summary.counts[event.kind] += 1;
      summary.events.push(event);
    }
  }
  return summary;
}
