# signal-radar

RSI(2) mean reversion signal scanner for US stocks. Generates daily buy/sell signals
for manual execution on SaxoBank.

## Strategy

- **RSI(2) Connors mean reversion** (published 2004, still profitable on tech large-caps)
- **Universe**: META, MSFT, GOOGL, NVDA (all validated)
- **Entry**: RSI(2) < 10 + Close > SMA(200) × 1.01
- **Exit**: Close > SMA(5) or Close < SMA(200)
- Long only, no stop-loss, ~2–5 day holding period
- Fee model: `us_stocks_usd_account` ($1 commission + 0.05% spread, no FX)

## Results (OOS 2014-2025, $10k, whole shares)

| Ticker | Trades | WR  | PF   | Robust | Verdict   |
|--------|--------|-----|------|--------|-----------|
| META   | 93     | 74% | 3.49 | 100%   | VALIDATED |
| MSFT   | 85     | 72% | 1.66 | 100%   | VALIDATED |
| GOOGL  | 90     | 67% | 1.72 | 100%   | VALIDATED |
| NVDA   | 96     | 67% | 1.48 | 100%   | VALIDATED |

100% of 48 parameter combinations profitable for all 4 validated stocks.
Pooled t-test: 508 trades, t=4.27, p=0.0000.

> **Requirement**: USD sub-account on Saxo mandatory. FX conversion (0.25%/trade on EUR
> account) destroys the edge.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run daily scanner (after US close ~22:00 CET)
python scripts/daily_scanner.py
```

## Docker (production)

```bash
cp .env.example .env          # fill TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
docker compose up -d          # starts scanner + cron (22:15 Sun–Fri, Europe/Zurich)
docker compose exec scanner python scripts/daily_scanner.py  # manual test run
docker compose logs -f scanner
```

## Manual Workflow (Saxo)

1. Run scanner after US close → BUY signal auto-written to `data/positions.json` as `pending`
2. Execute buy at next open on Saxo → update `positions.json`: `"status": "open"`, add `"entry_price"`
3. Scanner detects SELL / SAFETY_EXIT → execute manually → reset position to `null`

## Framework

Signal-radar includes a modular backtesting framework:

```bash
# Validate RSI(2) on US stocks ($10k, whole shares)
python -m cli.validate rsi2_stocks

# Validate RSI(2) on US ETFs ($100k, fractional)
python -m cli.validate rsi2_etfs
```

Adding a new strategy:

1. Create `strategies/my_strategy.py` inheriting `BaseStrategy`
2. Implement `check_entry()`, `check_exit()`, `default_params()`, `param_grid()`
3. Add a preset in `cli/validate.py`
4. Run `python -m cli.validate my_preset`

The pipeline automatically runs: backtest -> robustness (48 param combos) -> sub-period stability -> t-test -> verdict (VALIDATED / CONDITIONAL / REJECTED).

## Project Structure

```text
strategies/
  base.py                    — BaseStrategy ABC
  rsi2_mean_reversion.py     — RSI(2) Connors plugin
  donchian_trend.py          — Donchian trend following plugin

engine/
  simulator.py               — Generic backtest engine (start_idx/end_idx)
  types.py                   — Direction, ExitSignal, Position, BacktestResult
  indicators.py              — SMA, EMA, RSI (Wilder), ATR, ADX, Donchian
  indicator_cache.py         — Indicator cache by asset and period
  fee_model.py               — FeeModel dataclass + presets
  notifier.py                — Telegram notifications

validation/
  pipeline.py                — validate() orchestrator
  robustness.py              — Parametric robustness (48 combos)
  sub_periods.py             — Sub-period stability
  statistics.py              — T-test significance
  report.py                  — Verdict + formatted report
  config.py                  — ValidationConfig

cli/
  validate.py                — CLI: python -m cli.validate <preset>

data/
  base_loader.py             — BaseDataLoader + to_cache_arrays()
  yahoo_loader.py            — YahooLoader (parquet cache, adj-close O/H/L)
  positions.json             — Live position state machine
  signal_history.csv         — Append-only signal log

scripts/
  daily_scanner.py           — [PRODUCTION] Daily signal scanner
  verify_migration.py        — Migration verification (old vs new engine)

config/
  production_params.yaml     — Frozen production params
  fee_models.yaml            — Fee model presets

deploy/
  entrypoint.sh / crontab / deploy.sh — Docker + cron deployment

docs/
  ROADMAP.md                 — Roadmap Phase 1-5
  PHASE2_RESULTS.md          — Phase 2 complete results
```

## Phase History

| Phase     | Description                                                           | Status      |
|-----------|-----------------------------------------------------------------------|-------------|
| Phase 1   | Backtesting engine + RSI(2) strategy validation on ETFs ($100k)       | COMPLETE    |
| Phase 2   | Pivot to individual stocks ($10k) + daily scanner + Docker + Telegram | COMPLETE    |
| Phase 3   | Modular backtesting framework + validation pipeline                   | COMPLETE    |
| Phase 4   | Live validation on Saxo (30+ real trades, go/no-go)                   | PLANNED     |
| Phase 5   | Web dashboard (equity curve, trade journal)                           | PLANNED     |
| Phase 6   | Scale up capital + expand universe                                    | PLANNED     |
| Phase 7   | Full automation via Saxo API                                          | VISION      |

See [docs/ROADMAP.md](docs/ROADMAP.md) for detailed planning.

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TZ=Europe/Zurich
```
