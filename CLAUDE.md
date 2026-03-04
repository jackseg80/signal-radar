# CLAUDE.md — signal-radar

## Project Status
Phase 1 COMPLETE -- Phase 2 COMPLETE -- Phase 3 COMPLETE -- Infra Scale-Up COMPLETE -- SQLite Unified DB COMPLETE -- Multi-Strategy Scanner COMPLETE -- FastAPI Dashboard API COMPLETE -- React Frontend Dashboard COMPLETE -- Docker Packaging COMPLETE -- CLI Container COMPLETE -- Scanner Trigger COMPLETE -- Live Trades COMPLETE -- Hardening Audit COMPLETE -- Backtest Audit COMPLETE -- Proximity Alerts COMPLETE -- Monthly Refresh COMPLETE -- Trade Journal COMPLETE -- Dashboard Polish COMPLETE -- Strategies Center COMPLETE.
Framework backtest modulaire operationnel. 443 tests.
Validated strategies : RSI(2) MR (10 stocks), IBS MR (13 stocks), TOM (21 stocks + 6 ETFs).
Base SQLite unique (data/signal_radar.db) : prix OHLCV + resultats + paper trading + live trades.
Scanner multi-strategie avec paper trading ($5k capital). Trigger manuel via dashboard.
API REST (FastAPI) + Frontend React (Vite + Tailwind v4 + Recharts). Live trades logging + paper vs live compare.
Proximity alerts : section "Approaching Trigger" dans le dashboard + mini-barres dans MarketOverview.
Monthly refresh : cli/runner.py (run_screen/run_validate importables) + scripts/monthly_refresh.py (cron 1er du mois).
Trade Journal : page /journal dans le dashboard -- timeline unifiee paper+live, signal context, slippage, notes editables.
Strategies Center : page /strategies -- visualisations interactives (RSI2, IBS, TOM) pour comprendre les signaux.

## Stack
Python 3.12+, pytest, numpy, pandas, scipy, yfinance, fastapi, uvicorn
Frontend : React 18, Vite, Tailwind CSS v4, Recharts, React Router, Framer Motion

## Commandes
- Tests : `pytest tests/ -v`
- Valider une strategie : `python -m cli.validate rsi2 us_stocks_large` (strategie + univers YAML)
- Screening rapide : `python -m cli.screen rsi2 us_stocks_large` (backtest simple, pas de robustesse)
- Comparer resultats : `python -m cli.compare` (tableau croise depuis validation_results/)
- Lister univers : `python -m cli.validate --list-universes`
- Lister strategies : `python -m cli.validate --list-strategies`
- Verifier migration : `python scripts/verify_migration.py`
- **Scanner quotidien : `python scripts/daily_scanner.py`** (apres cloture US ~22h CET)
- Params production : `config/production_params.yaml`
- Docker build : `docker compose build`
- Docker demarrer : `docker compose up -d`
- Docker test scanner : `docker compose exec scanner python scripts/daily_scanner.py`
- Docker logs scanner : `docker compose logs -f scanner`
- Docker logs api : `docker compose logs -f api`
- **Dashboard prod : `http://192.168.1.200:9000`** (LAN apres deploiement)
- Deploy serveur : `bash deploy/deploy.sh` (git pull + docker compose build + up)
- **API Dashboard : `uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload`**
- API health : `curl http://localhost:8000/api/health`
- API docs : `http://localhost:8000/docs` (Swagger auto-genere)
- **Frontend dev : `cd frontend && npm run dev`** (http://127.0.0.1:3001)
- Frontend build : `cd frontend && npm run build`

### Donnees et analyse

- Lister assets en DB : `python -m cli.data info`
- Telecharger univers : `python -m cli.data download us_stocks_large`
- Mettre a jour : `python -m cli.data update us_stocks_large` (incremental)
- Mettre a jour tout : `python -m cli.data update --all`
- Vider donnees : `python -m cli.data clear [symbol]`
- Meilleurs assets : `python -m cli.analyze best rsi2 --min-pf 1.3`
- Tableau croise : `python -m cli.analyze compare us_stocks_large`
- Detail symbol : `python -m cli.analyze asset META`
- Vue d'ensemble : `python -m cli.analyze summary`

## Règles
- JAMAIS modifier scalp-radar (D:\Python\scalp-radar\ = lecture seule)
- JAMAIS importer depuis scalp-radar — tout est copié et indépendant
- Tous les tests doivent passer avant commit
- Type hints + docstrings obligatoires
- Data loader toujours via BaseDataLoader (jamais yfinance en dur)
- Tests gap-aware = priorité #1 (ne pas avancer sans qu'ils passent)

## Strategie validee : RSI(2) Mean Reversion

Universe : META, MSFT, GOOGL, NVDA (tous VALIDATED par le pipeline Phase 3)

Params (Connors canonical, NON optimises) :
- RSI(2) < 10 entry
- SMA(200) x 1.01 trend filter (buffer anti-whipsaw)
- SMA(5) exit (close > SMA5)
- Pas de stop-loss, position_fraction=0.2, long-only

Fee model : us_stocks_usd_account (compte USD Saxo, spread 0.05%)

Resultats pipeline Phase 3 -- OOS 2014-2025 ($10k whole shares) :

- META : 93 trades, PF 3.49, WR 74%, 100% robust, stable, significatif -- VALIDATED
- MSFT : 85 trades, PF 1.66, WR 72%, 100% robust, stable, significatif -- VALIDATED
- GOOGL : 90 trades, PF 1.72, WR 67%, 100% robust, stable, significatif -- VALIDATED
- NVDA : 96 trades, PF 1.48, WR 67%, 100% robust, stable, significatif -- VALIDATED
- AMZN : 74 trades, PF 1.39, WR 65%, 88% robust, instable, non-signif -- REJECTED
- GS : 70 trades, PF 1.55, WR 64%, 50% robust, stable, significatif -- REJECTED
- T-test poole : 508 trades, t=4.27, p=0.0000

Note : les PnL par trade sont identiques a Phase 2 (verifie par verify_migration.py).
La difference de nombre de trades vient du warmup ameliore dans le nouveau pipeline.

Resultats precedents ETFs OOS 2014-2025 ($100k) :

- 380 trades, WR 69%, PF 1.36, Sharpe 0.65 (viable a $100k, pas a $10k)

## Strategie validee : IBS Mean Reversion (Phase 3 addendum)

IBS = (Close - Low) / (High - Low). Entry IBS < 0.2 + close > SMA200. Exit IBS > 0.8 ou close > high[j-1].
Presets : `ibs_stocks` (12 assets), `ibs_etfs` (5 ETFs).

Resultats OOS 2014-2025 ($10k whole shares) :

- META : 302 trades, PF 1.68, WR 72%, 100% robust -- VALIDATED
- MSFT : 308 trades, PF 1.52, WR 69%, 100% robust -- VALIDATED
- GOOGL : 277 trades, PF 1.29, WR 66%, 97% robust -- VALIDATED
- NVDA : 314 trades, PF 2.07, WR 72%, 100% robust -- VALIDATED
- AMZN : 267 trades, PF 1.46, WR 63%, 100% robust -- VALIDATED
- AAPL : 289 trades, PF 1.51, WR 69%, 100% robust -- VALIDATED
- GS, TSLA, JPM, KO, JNJ, XOM -- REJECTED (PF < 1.1 ou robustesse < 70%)
- T-test poole : 3091 trades, t=3.81, p=0.0001

Resultats ETFs OOS 2014-2025 ($100k fractional) :

- QQQ : 265 trades, PF 1.45, WR 68%, 100% robust -- VALIDATED
- SPY : 269 trades, PF 1.21, WR 66%, 100% robust -- CONDITIONAL (non-signif)
- EFA : 225 trades, PF 1.38, WR 72%, 81% robust -- CONDITIONAL (instable)
- IWM, DIA -- REJECTED

## Strategie validee : Turn of the Month / TOM (Phase 3 addendum)

Signal calendaire pur. IBS = (Close - Low) / (High - Low) n'est pas utilise ici.
Entry : derniers N jours de trading du mois (default N=5). Exit : M-eme jour de trading du nouveau mois (default M=3).
Presets : `tom_stocks` (6 assets), `tom_etfs` (5 ETFs).
Param grid : entry_days_before_eom [3,4,5,6] x exit_day_of_new_month [2,3,4] = 12 combos.

Architecture specifique :

- `engine/indicator_cache.py` -- `build_cache(dates=...)` calcule `trading_day_of_month` + `trading_days_left_in_month`
- Warmup = 30 (pas d'indicateur technique, juste 1 mois minimum)
- Completement decorele de RSI(2) et IBS (signal calendaire vs technique)

Resultats OOS 2014-2025 ($10k whole shares) :

- META : 132 trades, PF 1.89, WR 64%, 100% robust, stable, significatif -- VALIDATED
- NVDA : 132 trades, PF 1.29, WR 58%, 100% robust, stable, significatif -- VALIDATED
- AAPL : 132 trades, PF 1.40, WR 59%, 100% robust, stable, significatif -- VALIDATED
- AMZN : 132 trades, PF 1.29, WR 58%, 100% robust, stable, significatif -- VALIDATED
- MSFT : 132 trades, PF 1.23, WR 53%, 100% robust, stable, non-signif -- CONDITIONAL
- GOOGL : 132 trades, PF 1.25, WR 56%, 100% robust, instable -- REJECTED
- T-test poole : 792 trades, t=3.90, p=0.0001

Resultats ETFs OOS 2014-2025 ($100k fractional) :

- SPY : 132 trades, PF 1.52, WR 61%, 100% robust -- VALIDATED
- QQQ : 132 trades, PF 1.47, WR 62%, 100% robust -- VALIDATED
- DIA : 132 trades, PF 1.42, WR 58%, 100% robust -- VALIDATED
- IWM : 132 trades, PF 1.06, WR 50%, 92% robust -- REJECTED
- EFA : 132 trades, PF 0.95, WR 52%, 42% robust -- REJECTED
- T-test poole : 660 trades, t=2.43, p=0.0076

## Stratégies/assets rejetés

1. Donchian TF sur US stocks (Steps 1-4) — WFO tout grade F (stocks mean-revertent)
2. Donchian TF sur forex majors (Step 8) — PF OOS 0.50 (range-bound post-2015)
3. RSI(2) sur GLD (Step 9) — PF OOS 0.95 (l'or trend, ne mean-revert pas)
4. RSI(2) sur TLT (Step 9) — PF OOS 1.04 (edge MR faible sur obligations)
5. RSI(2) sur XLE (Step 9) — PF OOS 1.02 (trop cyclique)
6. RSI(2) sur AMZN — PF 0.92 en 2019-2025 (instable)
7. RSI(2) sur GS — 48% combos profitables (fragile, dépend des params)
8. RSI(2) sur JPM, JNJ, TSLA, KO, XOM, CAT, WMT, AMD, AAPL — PF < 1.3 OOS
9. IBS sur GS, TSLA, JPM, KO, JNJ, XOM — PF < 1.1 ou robustesse < 70%
10. IBS sur IWM, DIA (ETFs) — PF < 1.0
11. TOM sur IWM, EFA (ETFs) — PF < 1.1 ou robustesse < 70%
12. TOM sur GOOGL (stocks) — instable OOS
13. TOM sur MSFT (stocks) — CONDITIONAL (non-significatif)

## Contraintes critiques

- Compte USD sur Saxo OBLIGATOIRE — FX 0.25%/trade tue l'edge court-terme
- Round-trip USD stocks : ~0.12% ($1 commission + 0.05% spread)
- Round-trip USD ETFs : ~0.07% ($1 commission + 0.03% spread)
- Round-trip EUR : ~0.55% → stratégie non viable en EUR

## Architecture

```
strategies/                            -- Phase 3 : plugins strategie
  base.py                              -- BaseStrategy ABC (check_entry, check_exit, init_state, warmup)
  rsi2_mean_reversion.py               -- RSI(2) Connors plugin
  ibs_mean_reversion.py                -- IBS Mean Reversion plugin (6 stocks VALIDATED)
  donchian_trend.py                    -- Donchian trend following plugin
  turn_of_month.py                     -- Turn of the Month plugin (4 stocks + 3 ETFs VALIDATED)

engine/
  types.py                             -- Direction, ExitSignal, Position, TradeResult, BacktestResult
  simulator.py                         -- Moteur unique generique (start_idx/end_idx pour IS/OOS)
  indicators.py                        -- SMA, EMA, Donchian, ATR, ADX, RSI (Wilder), IBS
  indicator_cache.py                   -- Build cache indicateurs par asset (SMA/RSI/IBS + arrays calendaires)
  fee_model.py                         -- FeeModel dataclass + presets (US_STOCKS_USD, US_ETFS_USD, etc.)
  backtest_config.py                   -- BacktestConfig (symbol, capital, slippage, fee_model)
  fast_backtest.py                     -- DEPRECATED -- ancien engine trend following
  mean_reversion_backtest.py           -- DEPRECATED -- ancien engine mean reversion
  notifier.py                          -- Telegram : send_telegram(), format_signal_message(), format_weekly_summary()

validation/                            -- Phase 3 : pipeline de validation
  pipeline.py                          -- validate() -- orchestrateur complet
  robustness.py                        -- Test 48 combos parametrique
  sub_periods.py                       -- Stabilite sous-periodes OOS
  statistics.py                        -- T-test significativite
  report.py                            -- Verdict + rapport formate + save_report() JSON
  config.py                            -- ValidationConfig

cli/                                   -- CLI
  validate.py                          -- python -m cli.validate <strategy> <universe>
  screen.py                            -- python -m cli.screen <strategy> <universe> (rapide, pas de robustesse)
  compare.py                           -- python -m cli.compare (tableau croise validation_results/)
  data.py                              -- python -m cli.data info/download/update/clear
  analyze.py                           -- python -m cli.analyze best/compare/asset/summary

data/
  db.py                                -- SignalRadarDB : base SQLite unique (prix OHLCV + resultats + paper trading + live trades)
  base_loader.py                       -- BaseDataLoader + to_cache_arrays()
  yahoo_loader.py                      -- YahooLoader, cache SQLite, adj-close O/H/L

optimization/
  walk_forward.py                      -- WFO fenetres en barres (trading days)
  overfit_detection.py                 -- Monte Carlo block bootstrap, DSR, stabilite

frontend/
  src/
    components/
      backtest/                      -- Compare Matrix, Validations Table, Screens Table
      journal/                       -- Filters, Stats, TradeCard, NoteEditor
      layout/                        -- Navbar, Sidebar, GuideModal
      live/                          -- LivePositions, PaperVsLive, LiveTradeForm
      market/                        -- MarketOverview
      performance/                   -- StrategyBreakdown, EquityCurve
      positions/                     -- OpenPositions, ClosedTrades
      signals/                       -- StrategySection, SignalCard, NearTrigger
      strategies/                    -- IBSVisualizer, RSI2Visualizer
      ui/                            -- Card, LoadingState, ErrorState, EmptyState
    pages/
      Dashboard.jsx                  -- Main command center
      Backtest.jsx                   -- Backtest results viewer
      Journal.jsx                    -- Trade journal timeline
      Strategies.jsx                 -- Educational playground with visualizers
    utils/                           -- format.js (colors, sorting, formatting)

tests/
  test_pipeline.py                     -- Tests pipeline validation (15 tests)
  test_simulator.py                    -- Tests moteur generique (15 tests)
  test_types.py                        -- Tests types framework (13 tests)
  test_rsi2_strategy.py                -- Tests RSI(2) plugin (19 tests)
  test_ibs_strategy.py                 -- Tests IBS plugin (23 tests)
  test_tom_strategy.py                 -- Tests TOM plugin (21 tests)
  test_universe_loader.py              -- Tests chargement univers YAML (8 tests)
  test_report_save.py                  -- Tests sauvegarde rapport JSON (4 tests)
  test_donchian_strategy.py            -- Tests Donchian plugin (27 tests)
  test_mean_reversion.py               -- Tests RSI(2) ancien moteur
  test_fee_model.py                    -- Tests fee model
  test_indicator_cache.py              -- Tests cache indicateurs
  test_fast_backtest.py                -- Tests ancien engine trend following
  test_daily_scanner.py                -- Tests scanner multi-strategie (RSI2+IBS+TOM, 33 tests)
  test_runner.py                       -- Tests cli/runner.py (constantes + run_screen + run_validate, 21 tests)
  test_monthly_refresh.py              -- Tests monthly_refresh.py (verdict diff + Telegram format, 18 tests)
  test_notifier.py                     -- Tests notifier Telegram
  test_data_loader.py                  -- Tests YahooLoader validation
  test_db.py                           -- Tests SignalRadarDB + paper trading + live trades + API methods + journal (57 tests)
  test_api.py                          -- Tests FastAPI endpoints + scanner trigger + live trades + journal (36 tests)
  conftest.py                          -- Fixtures partagees

scripts/
  daily_scanner.py                     -- Scanner multi-strategie RSI2+IBS+TOM + paper trading [PRODUCTION]
  monthly_refresh.py                   -- Refresh backtests (screens+validations) mensuel [PRODUCTION]
  compare_ibs_exit_timing.py           -- Compare IBS exit close[i] vs open[i+1] (audit biais)
  verify_migration.py                  -- Verification ancien moteur = nouveau framework
  validate_rsi2_*.py                   -- DEPRECATED -- anciens scripts validation Phase 1-2
  validate_donchian_forex.py           -- DEPRECATED -- Donchian forex (rejete)
  validate_sizing.py                   -- DEPRECATED -- Sizing impact
  optimize.py                          -- DEPRECATED -- Demo Donchian

config/
  production_params.yaml               -- Config scanner multi-strategie ($5k, 3 strategies, paper trading)
  fee_models.yaml                      -- Modeles de frais
  universe_loader.py                   -- Charge les univers YAML (load_universe, list_universes)
  universes/                           -- Univers d'assets YAML
    us_stocks_large.yaml               -- ~45 large cap US stocks
    us_etfs_broad.yaml                 -- 10 ETFs broad market
    us_etfs_sector.yaml                -- 11 sector ETFs (SPDR)
    forex_majors.yaml                  -- 7 paires forex majeures
  assets_etf_us.yaml                   -- LEGACY -- ancien univers ETFs
  assets_forex.yaml                    -- LEGACY -- 7 paires forex majeures

api/                                   -- FastAPI Dashboard API
  app.py                               -- FastAPI app, CORS (GET+POST), lifespan, routes + StaticFiles SPA mount
  config.py                            -- Settings (DB_PATH, load_production_config)
  dependencies.py                      -- get_db() singleton
  routes/
    signals.py                         -- GET /api/signals/today, /history
    positions.py                       -- GET /api/positions/open, /closed
    performance.py                     -- GET /api/performance/summary, /equity-curve
    market.py                          -- GET /api/market/overview
    backtest.py                        -- GET /api/backtest/screens, /validations, /compare
    scanner.py                         -- POST /api/scanner/run, GET /api/scanner/status
    live.py                            -- POST /api/live/open, /close ; GET /api/live/open, /closed, /summary, /compare
    journal.py                         -- GET /api/journal/entries ; PATCH /api/journal/paper/{id}/notes, /live/{id}/notes

Dockerfile                             -- Scanner image (cron + uv + python:3.12-slim) -- inclut cli/ validation/ strategies/
Dockerfile.api                         -- API image (uvicorn + frontend/dist/ + scanner code + numpy/yfinance/loguru + HEALTHCHECK)
requirements-api.txt                   -- Deps API + scanner (fastapi, uvicorn, pandas, pyyaml, numpy, yfinance, loguru)

deploy/
  entrypoint.sh                        -- Ecrit env vars cron + passthrough CMD
  crontab                              -- 22h15 dim-ven (TZ=Europe/Zurich)
  deploy.sh                            -- Script deploiement serveur Ubuntu (git pull + npm build + docker)
  README.md                            -- Instructions deploiement serveur

docs/
  PHASE1_RESULTS.md                    -- Resultats complets Phase 1
  PHASE2_STOCKS_RESULTS.md             -- Resultats Steps 11-13
  PHASE2_RESULTS.md                    -- Phase 2 complete
  ROADMAP.md                           -- Roadmap Phase 1-5
```
