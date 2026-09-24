# R1-05 fresh provider receipt collection

- 범위: US, `2025-09-11`~`2026-09-11`, fixed sample `100`, request budget `1000`.
- 실행: `market_research_cli collect --market US --env-file .env` with a new cache; no PAPER/live/order or remote mutation.
- Receipt: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-cache-0941/completed.json` (SHA-256 `2df1798a598494d1bb9a16696488c2b4e55fecf4e81fd5c0ae0e72d8089a89c5`).
- Result: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-result.json` (SHA-256 `a42fd8b4f53f1f05f39637dcff34806fa0fad17de6ad467acc40e0ae2a11ed7f`).
- Cache manifest: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/fresh-cache-0941/manifest.json` (SHA-256 `86b52a2445e9633ea4e022a9c9e123b217e69df0aa6e4d683ce823bb7fd570da`).

## Evidence and limits

- Raw receipt counts: Alpha Vantage `2`, Yahoo `76`, FRED `59`; capture window `2026-09-24T00:40:57Z`–`00:41:42Z`.
- Coverage: expected `27,472`, actual/retained `20,306`, missing `7,166`; result remains partial/insufficient for economic acceptance.
- This receipt improves request/checkpoint provenance but does not prove complete historical provider coverage, corporate-action completeness, opening positions, terminal marks, or benchmark/future observations. R1-05 checkbox and economic evaluation remain unchanged.
