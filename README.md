# Signal Radar 4.0.0

Signal Radar is a research and decision-support application for daily US stock signals. It scans RSI(2), IBS and Turn of the Month setups, evaluates their data and portfolio constraints, and prepares candidates for manual review. It does not connect to Saxo and never transmits brokerage orders.

## What changed in 4.0

- Signals are evaluated after the XNYS close for a possible next-session opening.
- The dashboard distinguishes a technical trigger, a real-account candidate, the shared paper portfolio and an independent virtual follow-up for each positive-score signal.
- The USD 5,000 shared paper portfolio is independent of Saxo. Opened, ignored or forgotten Saxo positions do not alter its trades. The virtual follow-up is also separate and uses a notional USD 5,000 per qualifying signal.
- Daily session checks use the XNYS calendar. Yahoo remains the main daily-price source; Nasdaq can fill an isolated, internally missing historical session after strict OHLC, neighboring-close and adjustment checks. Unresolved or conflicting prices fail closed.
- The dashboard records account confirmations, source and target sessions, eligibility reasons, price repairs and observation notes.

## Current operating status

As of 25 September 2026, the application is deployed for observation. The seven missing 22 September bars for COST, GE, HD, LLY, MA, UNH and V were verified from Nasdaq and recorded with their provenance. The latest production scan found no missing data among the configured titles.

The production validation currently covers 37 symbol/strategy pairs with no price-data errors. It has not established a pair as eligible for real-buy recommendations: Saxo costs remain provisional and current validation gates still apply. The 20-session observation is not complete. A repaired data series alone does not authorize an order.

## Strategies and execution assumptions

- RSI(2) mean reversion
- IBS mean reversion
- Turn of the Month (TOM)

The scanner forms signals after the close and targets the next session's open. Backtests and paper fills use executable prices and account for gaps; an opening price is not guaranteed for a market order. Adjusted prices are reserved for indicators, with split and dividend handling kept distinct from execution prices.

Historical strategy results are research evidence, not current purchase recommendations. Fees and slippage must be calibrated against executed Saxo USD statements before net performance is treated as verified. Do not use prior validation tables as a substitute for the current production validation report.

## Run locally

Python 3.12+ and Node.js are required.

~~~bash
pip install -e ".[dev,api,analysis]"
pytest tests/ -q

# Dashboard API
uvicorn api.app:app --reload

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
~~~

The API is available at http://127.0.0.1:8000; the Vite development server prints its local address.

## Docker

~~~bash
cp .env.example .env
docker compose up -d --build
~~~

The dashboard is served on port 9000. See deploy/README.md before touching an existing server. The legacy deployment script force-resets its checkout, stops the compose project, removes orphans and prunes Docker images; it must not be used as a routine update on a server with other workloads.

## Documentation

- Next-open model, data controls and rollback guidance: docs/NEXT_OPEN_V2.md
- Roadmap and current project status: docs/ROADMAP.md
- 4.0.0 release notes: docs/RELEASE_NOTES.md
- Deployment guide and safety limits: deploy/README.md

## Project structure

~~~text
api/               FastAPI dashboard and account/observation endpoints
config/            Strategy settings, fee assumptions and verified price repairs
data/              SQLite persistence, Yahoo loader and Nasdaq fallback
engine/            Indicators, calendar, ranking, fees and simulation
frontend/          React dashboard
scripts/           Daily scanner and validation tools
strategies/        RSI(2), IBS and TOM rules
validation/        Next-open and statistical validation
tests/             Regression and gap-aware tests
~~~

## Environment

TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are optional. TZ defaults to Europe/Zurich. Keep .env, database files, broker statements and server backups out of version control.
