<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Research reports and beginner language

- Research report actions must open a complete, readable web page. Do not make users download Markdown files or expose filename-only report actions. CSV and JSON data exports remain separate.
- Use the typed allowlist in `lib/research-reports.ts`. Never fetch an arbitrary URL or filesystem path supplied by a route or Markdown link. History report bytes must match the requested artifact SHA-256; portfolio and dividend run IDs are not report hashes.
- Render full report text with safe Markdown components. Preserve original numbers and wording, render embedded HTML as inert text, and never enable MDX, raw HTML execution, or automatic external images. Known report links open canonical web readers; unsupported Markdown files are inactive descriptive text.
- Comparison labels describe simulated research settings, not the user's prior investment method or current holdings. Prefer `연구용 비교 설정` and `변경해서 시험한 설정`. Only show specific rules after the study ID and source/result/report hashes match the registered narrative.
- Show the research purpose and verified setting differences before the associated metrics. Explain who acts, what gets recalculated, and a concrete hypothetical holding decision before introducing 4/8 weeks as the interval. Converting weeks to days alone is not a comprehension fix. Trades depend on conditions such as weight bands; protective sales may occur between reviews. A volatility target is neither a promised return nor a maximum loss guarantee.
- Keep original report wording intact. Put beginner explanations in the reader introduction or glossary rather than silently rewriting historical evidence.


# Novice comprehension review

- Design the reading path around purpose, the researchers' comparison, actual actions, observed results and limits, then the reader's next step. Prefer a short explanation in the right place to additional cards or a glossary wall.
- Keep illustrative money examples visibly separate from actual historical results and investment recommendations. Explain conditional trades and protective sales; never imply a schedule guarantees transactions or ends the investment.
- Before completing a user-facing research change, use an independent reviewer with no implementation context. The reviewer may see only rendered screens and normal navigation, not source, plans, API payloads or implementation explanations.
- Ask the reviewer to explain the page purpose, who created the comparison and why, the actions and time intervals, what the results do and do not establish, and the reader's next action. Each answer needs visible text and a URL as evidence. Filling a gap with finance knowledge is a failed check.
- Fix material comprehension gaps and recheck the rendered screen. Code checks and browser layout checks do not replace this review. Record that agent review simulates a novice; do not claim a real participant study.
- Preserve full web reports. Add visible instructions for horizontally scrolling wide tables, and explain display precision differences when summaries and original reports use different formatting.

- Evaluate scan effort as well as whether every sentence can be understood. Put a short, data-matched conclusion near the purpose/question. Prefer aligned condition tables, paired metric bars and compact action sequences over duplicate paragraphs. Keep adverse risk and total costs visible alongside return.
- Charts must use observed values, direct labels, a shared zero-based scale within each metric and explicit units. Different metrics use different scales. Preserve signed returns, true zero and missing-data distinctions; never invent a price or return time series from aggregate results. Color identifies the trial and must not imply that a larger drawdown is better. Keep the original decimal labels and comparison logic; approximate only display geometry.
