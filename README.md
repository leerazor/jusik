# Jusik

A local, read-only dashboard for domestic and overseas stock holdings at Korea Investment & Securities (KIS). The frontend uses Next.js App Router, React and TypeScript. The backend uses Python 3.13 and FastAPI.

## Run locally

Use two terminals from the repository root. Keep both servers bound to loopback: this version has no user authentication and is intended for a single user's local machine.

Backend:

```bash
pyenv install -s 3.13.15
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
backend/.venv/bin/python -m uvicorn jusik.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend:

```bash
nvm install
nvm use
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. The first page visit requests an access token and reads account balances. Credentials and account identifiers stay in the backend. No order endpoints are implemented or called.

## Configuration

The backend explicitly loads `.env.prod` in the repository root. Preserve your existing file. For a new installation, copy `.env.example` to `.env.prod` and fill in values locally. Never commit real credentials or account identifiers. `.env.dev` is not loaded: this dashboard uses production account **read access**, not simulated balances. Only the official production KIS base URL is accepted. Environment variables override file values.

The backend holds its access token in memory and reuses it until shortly before expiry. Keep a single backend worker running; frequent restarts can hit KIS token issuance limits. Authentication failures impose a one-minute retry cooldown. Balance requests are spaced at least one second apart to reduce broker throttling. Portfolio responses are cached for 30 seconds inside the backend; browser and Next.js data caches are disabled. Refreshing within 30 seconds returns the existing snapshot with its original timestamp.

## Coverage and meaning

- Korea, US (NASD production query covers US exchanges), Hong Kong, Shanghai, Shenzhen, Japan, Hanoi and Ho Chi Minh City.
- Balance API snapshots, not streaming quotes. Prices may be delayed, particularly during market closures. Query completion timestamps are UTC internally and shown in Korea time; they are not exchange quote timestamps.
- Position quantity, average acquisition price, current price, acquisition amount, valuation, unrealized profit and calculated return.
- Separate totals for KRW, USD, HKD, CNY, JPY and VND. No FX conversion or mixed-currency grand total. Cash, realized profit and other asset classes are excluded.
- Decimal arithmetic on the backend; financial values cross the API as strings. Returns use half-up rounding to two decimal places. Display-only price precision is truncated without floating-point arithmetic. Zero cost has an undefined return, displayed as a dash.
- All continuation pages must succeed for a market to be included. Identical repeated positions are deduplicated; conflicting repeated positions fail that market, avoiding silent double counting. Zero-quantity positions are omitted.
- Market failures are shown explicitly. Totals only include successful markets and are labeled partial if any market failed. Missing or invalid numeric fields fail validation instead of silently becoming zero.
- No database or historical performance chart: those require persisting dated snapshots.

## Checks

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy jusik
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

Tests use mocked KIS responses and never place orders. They cover decimal precision, zero/negative/missing values, duplicates, continuation failures, currency separation, weekend/timezone boundaries, cache coalescing, and redacted errors. Partial fills and canceled/rejected orders are not processed by this application; KIS provides the resulting holdings.

## GitHub

If no remote exists, create an empty private GitHub repository without an initial README or license. Then set its URL using `git remote add origin https://github.com/YOUR_USERNAME/jusik.git`. If Git is not initialized yet, first run `git init -b main`.

Before committing, run `git status --short`, `git check-ignore .env.prod .env.dev` and inspect `git diff --cached`. Stage only project code and placeholder configuration. Push your initial commit with `git push -u origin main`. Never force-add ignored environment files. This setup does not automatically commit, create a remote repository or push.

## API references

- [KIS domestic balance example](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py)
- [KIS overseas balance example](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py)
- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
