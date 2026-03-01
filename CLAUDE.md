# CLAUDE.md — signal-radar

## Project Status
Phase 1 COMPLETE — Phase 2 COMPLETE (daily signal scanner opérationnel).
Validated strategy : RSI(2) mean reversion, 3 stocks + 1 watchlist, params Connors canonical.

## Stack
Python 3.12+, pytest, numpy, pandas, scipy, yfinance

## Commandes
- Tests : `pytest tests/ -v`
- Validation finale : `python scripts/validate_rsi2_final.py`
- **Scanner quotidien : `python scripts/daily_scanner.py`** (après clôture US ~22h CET)
- Params production : `config/production_params.yaml`
- Docker build : `docker compose build`
- Docker démarrer : `docker compose up -d`
- Docker test scanner : `docker compose exec scanner python scripts/daily_scanner.py`
- Docker logs : `docker compose logs -f scanner`

## Règles
- JAMAIS modifier scalp-radar (D:\Python\scalp-radar\ = lecture seule)
- JAMAIS importer depuis scalp-radar — tout est copié et indépendant
- Tous les tests doivent passer avant commit
- Type hints + docstrings obligatoires
- Data loader toujours via BaseDataLoader (jamais yfinance en dur)
- Tests gap-aware = priorité #1 (ne pas avancer sans qu'ils passent)

## Stratégie validée : RSI(2) Mean Reversion

Universe : META, MSFT, GOOGL (validés) + NVDA (watchlist)

Params (Connors canonical, NON optimisés) :
- RSI(2) < 10 entry
- SMA(200) × 1.01 trend filter (buffer anti-whipsaw)
- SMA(5) exit (close > SMA5)
- Pas de stop-loss, position_fraction=0.2, long-only

Fee model : us_stocks_usd_account (compte USD Saxo, spread 0.05%)

Résultats stocks OOS 2014-2025 ($10k whole shares) :

- Poolé 15 stocks : 1063 trades, WR 65%, PF 1.30, Sharpe 0.69, t-test p=0.0116
- META : PF 2.98, WR 74%, 100% robust, stable, p=0.0003
- MSFT : PF 1.74, WR 73%, 100% robust, stable, p=0.057
- GOOGL : PF 1.66, WR 68%, 100% robust, stable, p=0.055
- NVDA : PF 1.48, WR 67%, 100% robust, stable, p=0.135 (watchlist)

Résultats précédents ETFs OOS 2014-2025 ($100k) :

- 380 trades, WR 69%, PF 1.36, Sharpe 0.65 (viable à $100k, pas à $10k)

## Stratégies/assets rejetés

1. Donchian TF sur US stocks (Steps 1-4) — WFO tout grade F (stocks mean-revertent)
2. Donchian TF sur forex majors (Step 8) — PF OOS 0.50 (range-bound post-2015)
3. RSI(2) sur GLD (Step 9) — PF OOS 0.95 (l'or trend, ne mean-revert pas)
4. RSI(2) sur TLT (Step 9) — PF OOS 1.04 (edge MR faible sur obligations)
5. RSI(2) sur XLE (Step 9) — PF OOS 1.02 (trop cyclique)
6. RSI(2) sur AMZN — PF 0.92 en 2019-2025 (instable)
7. RSI(2) sur GS — 48% combos profitables (fragile, dépend des params)
8. RSI(2) sur JPM, JNJ, TSLA, KO, XOM, CAT, WMT, AMD, AAPL — PF < 1.3 OOS

## Contraintes critiques

- Compte USD sur Saxo OBLIGATOIRE — FX 0.25%/trade tue l'edge court-terme
- Round-trip USD stocks : ~0.12% ($1 commission + 0.05% spread)
- Round-trip USD ETFs : ~0.07% ($1 commission + 0.03% spread)
- Round-trip EUR : ~0.55% → stratégie non viable en EUR

## Architecture

```
engine/
  indicators.py              — SMA, EMA, Donchian, ATR, ADX, RSI (Wilder)
  indicator_cache.py         — Build cache indicateurs par asset (SMA/RSI by period)
  fee_model.py               — FeeModel dataclass + presets (US_STOCKS_USD, US_ETFS_USD, etc.)
  backtest_config.py         — BacktestConfig (symbol, capital, slippage, fee_model)
  fast_backtest.py           — Engine trend following (Donchian/EMA, trailing ATR stop)
  mean_reversion_backtest.py — Engine RSI(2) mean reversion (SMA filter, SMA exit)
  notifier.py                — Telegram : send_telegram(), format_signal_message(), format_weekly_summary()

data/
  base_loader.py             — BaseDataLoader + to_cache_arrays()
  yahoo_loader.py            — YahooLoader, cache parquet, adj-close O/H/L

optimization/
  walk_forward.py            — WFO fenêtres en barres (trading days)
  overfit_detection.py       — Monte Carlo block bootstrap, DSR, stabilité

tests/
  test_mean_reversion.py     — Tests RSI(2) (entry, exit, gap SL, anti-look-ahead)
  test_fee_model.py          — Tests fee model
  test_indicator_cache.py    — Tests cache indicateurs
  test_fast_backtest.py      — Tests engine trend following
  test_daily_scanner.py      — Tests scanner (signaux, pending, watchlist)
  test_notifier.py           — Tests notifier Telegram
  test_data_loader.py        — Tests YahooLoader validation
  conftest.py                — Fixtures partagées

scripts/
  daily_scanner.py           — Scanner quotidien RSI(2) [PRODUCTION]
  validate_rsi2_final.py     — Step 10 : validation portfolio final 5 ETFs [REFERENCE]
  validate_rsi2_spy.py       — Step 5  : RSI(2) sur SPY seul, comparaison fees
  validate_rsi2_portfolio.py — Step 6  : Portfolio 4 ETFs equity, IS/OOS
  validate_rsi2_robustness.py— Step 7  : Monte Carlo + sensibilité 48 combos ETFs
  validate_rsi2_expanded.py  — Step 9  : Univers élargi GLD/TLT/XLE/EFA
  validate_rsi2_stocks.py    — Step 11 : 15 actions US individuelles, $10k whole shares
  validate_rsi2_stocks_robustness.py — Step 12 : Robustesse 6 candidats (48 combos, sous-périodes, t-test)
  validate_sizing.py         — Sizing impact $100k vs $10k, fractional vs whole
  validate_donchian_forex.py — Step 8  : REJECTED — Donchian forex PF OOS 0.50

config/
  production_params.yaml     — Params production figés pour Phase 2
  fee_models.yaml            — Modèles de frais (us_stocks, us_stocks_usd, us_etfs_usd, forex, eu)
  assets_etf_us.yaml         — Univers ETFs equity US (SPY/QQQ/IWM/DIA)
  assets_forex.yaml          — 7 paires forex majeures (rejeté)

deploy/
  entrypoint.sh              — Écrit env vars cron + passthrough CMD
  crontab                    — 22h15 dim-ven (TZ=Europe/Zurich)
  deploy.sh                  — Script déploiement serveur Ubuntu
  README.md                  — Instructions déploiement serveur

docs/
  PHASE1_RESULTS.md          — Résultats complets Phase 1 (ETFs, stratégies rejetées)
  PHASE2_STOCKS_RESULTS.md   — Résultats Steps 11-13 : stocks individuels, robustesse, univers production
  PHASE2_RESULTS.md          — Phase 2 complète : stocks + scanner + Docker + Telegram
```

## Conventions techniques

- Anti-look-ahead : signal sur [i-1], action sur open[i]
- Gap-aware exits : vérifier open vs SL avant le intraday
- Force-close fin de données : EXCLU de trade_pnls (biais)
- Méthodologie split IS/OOS : slicer le DataFrame avant l'engine (SMA recalculée proprement)
- t-test pour signification statistique MR (block bootstrap teste l'ordre, pas la sélection)
- `to_cache_arrays(df)` : fonction module-level dans `data/base_loader.py`
- `holding_days_out` : liste vide passée à `_simulate_mean_reversion` pour durées trades
- FeeModel : `entry_fee` inclus dans le PnL retourné par `_close_trend_position`
  → ne PAS soustraire à nouveau dans `capital +=` (bug corrigé en Phase 1)

## Phase 2 — Scanner quotidien (COMPLETE)

`scripts/daily_scanner.py` — opérationnel depuis 2026-03-01.

Architecture :
- `evaluate_signal(rsi2, close, sma200, sma5, position, ..., watchlist=False)` → `SignalResult` — fonction pure, testable
- Signaux : BUY / SELL / SAFETY_EXIT / HOLD / NO_SIGNAL / PENDING_VALID / PENDING_EXPIRED / WATCH
- `data/positions.json` — state machine position : null → pending (auto) → open (manuel) → null (manuel)
- `data/signal_history.csv` — log append-only (timestamp, symbol, signal, rsi2, close, sma200, sma5, entry_price, notes)
- `logs/scanner.log` — log rotatif debug (loguru, 1 MB, 30 jours)

Workflow manuel Saxo :

1. Lancer scanner après clôture US (~22h CET)
2. Si BUY → pending écrit auto dans positions.json → exécuter au open du lendemain sur Saxo
3. Mettre à jour positions.json manuellement : `"status": "open"`, ajouter `"entry_price"`
4. Scanner détecte SELL/SAFETY_EXIT → exécuter manuellement → remettre null dans positions.json

Cohérence anti-look-ahead :
- Entry : signal sur today (= backtest [i-1]), action demain au open (= [i]) ✓
- Exit : évalué sur today's close, exécuté au open suivant (slippage documenté, intentionnel)

## Phase 3 — Déploiement Docker + Telegram (COMPLETE)

Conteneurisation et automatisation du scanner quotidien.

Architecture :
- `engine/notifier.py` — `send_telegram()` (urllib stdlib) + `format_signal_message()` + `format_weekly_summary()`
  - ⚠️ `r.notes` contient `<` et `>` (ex. "RSI=7.4 < 10.0") → toujours `html.escape(r.notes)` avec `parse_mode="HTML"`
- `Dockerfile` — python:3.12-slim + uv + cron ; `ENTRYPOINT ["/entrypoint.sh"]` + `CMD []`
- `docker-compose.yml` — service scanner, volumes data/logs/config:ro, restart unless-stopped
- `deploy/entrypoint.sh` — écrit env vars pour cron (`/app/.env.cron`) ; passthrough `if [ $# -gt 0 ]; then exec "$@"; fi` avant `exec cron -f`
  - Permet : `docker compose exec scanner python scripts/daily_scanner.py`
- `deploy/crontab` — 22:15 dim-ven (TZ=Europe/Zurich)

Notifications Telegram :
- BUY/SELL/SAFETY_EXIT → message immédiat
- WATCH avec trigger BUY → inclus dans le message
- Silence si aucun signal actionnable (pas de spam quotidien)
- Rapport hebdo dimanche soir même sans signal

Déploiement serveur Ubuntu (192.168.1.200) :
```bash
cp .env.example .env  # remplir TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
bash deploy/deploy.sh
docker compose exec scanner python scripts/daily_scanner.py  # test
```

Variables d'environnement : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TZ=Europe/Zurich`
