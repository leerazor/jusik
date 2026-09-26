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
- Show verified setting differences before the associated metrics. Explain 4/8 weeks as 28/56 calendar days between scheduled reviews of target holding weights, not the investment horizon or guaranteed trades. Trades depend on conditions such as weight bands; protective sales may occur between reviews. A volatility target is neither a promised return nor a maximum loss guarantee.
- Keep original report wording intact. Put beginner explanations in the reader introduction or glossary rather than silently rewriting historical evidence.
