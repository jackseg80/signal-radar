# signal-radar

A comprehensive quantitative trading platform for US stocks and ETFs, specializing in Mean Reversion and Seasonal strategies. It provides a modular backtesting framework, an automated daily scanner, and a web dashboard for performance tracking.

## Key Features

- **Multi-Strategy Scanner**: Automated daily scanning for RSI(2), IBS, and Turn-of-the-Month signals.
- **Modular Framework**: Generic simulation engine with realistic fee models, gap-aware execution, and slippage.
- **Validation Pipeline**: Automated robustness testing (48 parameter combinations), sub-period stability analysis, and statistical significance (T-tests).
- **Web Dashboard**: Modern React interface (Vite + Tailwind v4) to visualize signals, equity curves, and proximity alerts.
- **Unified SQLite DB**: Single source of truth for OHLCV data, backtest results, and trade logs.
- **Telegram Notifications**: Instant alerts for entry/exit signals and weekly performance summaries.

## Strategies

1. **RSI(2) Mean Reversion**: Exploits short-term oversold conditions (Connors).
2. **IBS (Internal Bar Strength)**: Mean reversion based on daily range positioning.
3. **Turn of the Month (TOM)**: Exploits seasonal calendar biases in US indices and large caps.
4. **Donchian Trend**: Trend-following framework (validated for Forex).

### Validated Universe (OOS 2014-2025)

| Strategy | Typical Assets | WR | PF | Status |
|----------|----------------|----|----|--------|
| **RSI(2)** | META, MSFT, NVDA, GOOGL | 70%+ | 1.6+ | **VALIDATED** |
| **IBS** | AAPL, MSFT, QQQ | 68%+ | 1.5+ | **VALIDATED** |
| **TOM** | SPY, QQQ, META, AAPL | 60%+ | 1.4+ | **VALIDATED** |

> **Requirement**: USD sub-account on Saxo/Interactive Brokers is mandatory. FX conversion fees (0.25%/trade) will destroy the edge of these short-term strategies.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev,api,analysis]"

# Run unit tests (440+ tests)
pytest tests/ -v

# Start local development API
uvicorn api.app:app --reload

# Start Frontend (in a separate terminal)
cd frontend && npm run dev
```

## Production (Docker)

The production stack includes the automated scanner (cron) and the dashboard API.

```bash
cp .env.example .env          # Fill TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, etc.
docker compose up -d          # Dashboard available at http://localhost:9000
```

## Workflow

1. **Daily Scan**: Automated at 22:15 CET (after US close). Signals are sent to Telegram and stored in the DB.
2. **Execution**: Review "Approaching Triggers" in the dashboard. If a BUY triggers, execute manually at the next market open.
3. **Logging**: Use the Dashboard to "Log Real Trade" from a paper position.
4. **Journaling**: Add notes and track slippage (Paper vs Live) in the unified Trade Journal.

## Engineering & Validation Rigor

This project goes beyond simple backtesting by implementing professional-grade quantitative validation tools:

- **Statistical Integrity**: Uses **Monte Carlo Block Bootstrap** and **Deflated Sharpe Ratio (DSR)** (via `optimization/overfit_detection.py`) to distinguish between true strategy edge and "backtest overfitting" (luck).
- **Walk-Forward Optimization**: Implements rolling window optimizations (`optimization/walk_forward.py`) to ensure strategies remain robust across different market regimes.
- **Execution Forensic**: Systematic auditing of execution biases. For instance, `scripts/compare_ibs_exit_timing.py` empirically proves that the IBS strategy remains conservative (and even more profitable) when using next-day open prices instead of same-day close.
- **Modern Tech Stack**: Built on **NumPy 2.0+** for vectorized performance and deployed using **uv** for ultra-fast, reproducible builds.
- **Unified State Management**: Fully migrated from legacy JSON/Parquet files to a robust **SQLite** architecture (`data/db.py`) ensuring ACID compliance for trade journals and paper trading logs.

## Project Structure

```text
api/               — FastAPI Dashboard API & Signal routes
frontend/          — React Dashboard (Vite + Tailwind v4 + Recharts)
strategies/        — Pluggable strategy logic (BaseStrategy)
engine/            — Simulation engine (simulator.py), fee models, and indicators
validation/        — Robustness & Statistical validation pipeline
cli/               — Command-line tools for validation and screening
data/              — SQLite DB manager (db.py) and Yahoo Finance loader
scripts/           — Production scanner and maintenance scripts
config/            — Asset universes (YAML) and production parameters
```

## Phase History

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1-3 | Backtest Engine, Modular Framework & Validation Pipeline | **COMPLETE** |
| Phase 4 | SQLite Migration & Multi-Strategy Scanner | **COMPLETE** |
| Phase 5 | Web Dashboard & Trade Journal | **COMPLETE** |
| Phase 6 | Proximity Alerts & Automated Monthly Refresh | **COMPLETE** |
| Phase 7 | Scale up capital + Expand Universe | **IN PROGRESS** |

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TZ=Europe/Zurich
```
