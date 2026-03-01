# signal-radar

RSI(2) mean reversion signal scanner for US stocks. Generates daily buy/sell signals
for manual execution on SaxoBank.

## Strategy

- **RSI(2) Connors mean reversion** (published 2004, still profitable on tech large-caps)
- **Universe**: META, MSFT, GOOGL (validated), NVDA (watchlist)
- **Entry**: RSI(2) < 10 + Close > SMA(200) × 1.01
- **Exit**: Close > SMA(5) or Close < SMA(200)
- Long only, no stop-loss, ~2–5 day holding period
- Fee model: `us_stocks_usd_account` ($1 commission + 0.05% spread, no FX)

## Results (OOS 2014–2025, $10k, whole shares)

| Ticker | Trades | WR  | PF   | Sharpe | p-value           |
|--------|--------|-----|------|--------|-------------------|
| META   | 84     | 74% | 2.98 | 1.09   | 0.0003            |
| MSFT   | 78     | 73% | 1.74 | 0.48   | 0.057             |
| GOOGL  | 78     | 68% | 1.66 | 0.49   | 0.055             |
| NVDA   | 86     | 67% | 1.48 | 0.34   | 0.135 (watchlist) |

100% of 48 parameter combinations profitable for all 3 validated stocks.

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

## Project Structure

```text
engine/
  indicators.py              — SMA, EMA, RSI (Wilder), ATR, ADX, Donchian
  indicator_cache.py         — Indicator cache by asset and period
  fee_model.py               — FeeModel dataclass + presets
  mean_reversion_backtest.py — RSI(2) backtest engine (gap-aware)
  notifier.py                — Telegram notifications

data/
  base_loader.py             — BaseDataLoader + to_cache_arrays()
  yahoo_loader.py            — YahooLoader (parquet cache, adj-close O/H/L)
  positions.json             — Live position state machine
  signal_history.csv         — Append-only signal log

scripts/
  daily_scanner.py           — [PRODUCTION] Daily signal scanner
  validate_rsi2_stocks.py    — Step 11: 15 US stocks screening
  validate_rsi2_stocks_robustness.py — Step 12: Robustness (48 combos, sub-periods, t-test)
  validate_sizing.py         — $100k vs $10k sizing comparison

config/
  production_params.yaml     — Frozen production params
  fee_models.yaml            — Fee model presets

deploy/
  entrypoint.sh / crontab / deploy.sh — Docker + cron deployment

docs/
  PHASE1_RESULTS.md          — Phase 1: ETF validation (historical reference)
  PHASE2_STOCKS_RESULTS.md   — Phase 2: Individual stocks screening & robustness
  PHASE2_RESULTS.md          — Phase 2 complete: stocks + scanner + Docker
```

## Phase History

| Phase     | Description                                                           | Status      |
|-----------|-----------------------------------------------------------------------|-------------|
| Phase 1   | Backtesting engine + RSI(2) strategy validation on ETFs ($100k)       | COMPLETE    |
| Phase 2   | Pivot to individual stocks ($10k) + daily scanner + Docker + Telegram | COMPLETE    |
| Phase 2.5 | Live validation on Saxo (30+ real trades, go/no-go)                   | IN PROGRESS |
| Phase 3   | Web dashboard (FastAPI + SQLite, equity curve, trade journal)         | PLANNED     |
| Phase 4   | Scale up capital + expand universe                                    | PLANNED     |
| Phase 5   | Full automation via Saxo API                                          | VISION      |

See [docs/ROADMAP.md](docs/ROADMAP.md) for detailed planning.

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TZ=Europe/Zurich
```
