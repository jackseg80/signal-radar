# CLAUDE.md — signal-radar

## Project Status
Phase 1 COMPLETE -- Phase 2 COMPLETE -- Phase 3 COMPLETE -- Infra Scale-Up COMPLETE -- SQLite Unified DB COMPLETE -- Multi-Strategy Scanner COMPLETE -- FastAPI Dashboard API COMPLETE -- React Frontend Dashboard COMPLETE -- Docker Packaging COMPLETE -- CLI Container COMPLETE -- Scanner Trigger COMPLETE -- Live Trades COMPLETE -- Hardening Audit COMPLETE -- Backtest Audit COMPLETE -- Proximity Alerts COMPLETE -- Monthly Refresh COMPLETE -- Trade Journal COMPLETE -- Dashboard Polish COMPLETE.
Framework backtest modulaire operationnel. 443 tests.
Validated strategies : RSI(2) MR (10 stocks), IBS MR (13 stocks), TOM (21 stocks + 6 ETFs).
Base SQLite unique (data/signal_radar.db) : prix OHLCV + resultats + paper trading + live trades.
Scanner multi-strategie avec paper trading ($5k capital). Trigger manuel via dashboard.
API REST (FastAPI) + Frontend React (Vite + Tailwind v4 + Recharts). Live trades logging + paper vs live compare.
Proximity alerts : section "Approaching Trigger" dans le dashboard + mini-barres dans MarketOverview.
Monthly refresh : cli/runner.py (run_screen/run_validate importables) + scripts/monthly_refresh.py (cron 1er du mois).
Trade Journal : page /journal dans le dashboard -- timeline unifiee paper+live, signal context, slippage, notes editables.

## Stack
Python 3.12+, pytest, numpy, pandas, scipy, yfinance, fastapi, uvicorn
Frontend : React 18, Vite, Tailwind CSS v4, Recharts, React Router

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

## Conventions techniques

- Anti-look-ahead entry : signal sur [i-1], action sur open[i]
- Exit close-based MR : signal sur close[i], exit a close[i] (mesure CONSERVATEUR vs open[i+1])
- SMA5 exit : close[i] > SMA5[i] ⟺ close[i] > mean(close[i-4:i]) (pas de look-ahead circulaire)
- Sharpe annualise avec sqrt(trades_per_year) (pas sqrt(252) -- per-trade returns, pas daily)
- Gap-aware exits : verifier open vs SL avant intraday
- Force-close fin de donnees : EXCLU de trade_pnls (biais)
- t-test pour signification statistique MR (block bootstrap teste l'ordre, pas la selection)
- `to_cache_arrays(df)` : fonction module-level dans `data/base_loader.py`
- FeeModel : `entry_fee` inclus dans le PnL retourne par `_close_trend_position`
  -> ne PAS soustraire a nouveau dans `capital +=` (bug corrige en Phase 1)
- Nouvelle strategie = 1 fichier dans strategies/ + herite BaseStrategy
- Validation = `python -m cli.validate <strategy> <universe>` -> rapport + verdict + sauvegarde JSON
- Screening = `python -m cli.screen <strategy> <universe>` -> tableau trie par PF (rapide)
- Univers YAML dans config/universes/ : ajouter un fichier = ajouter un univers testable
- Les anciens moteurs (fast_backtest.py, mean_reversion_backtest.py) sont DEPRECATED
- simulator.py est le seul moteur a utiliser pour tout nouveau backtest
- start_idx/end_idx dans simulate() pour IS/OOS slicing (pas de reconstruction de cache)

## Phase 2 — Scanner multi-strategie + Paper Trading (COMPLETE)

`scripts/daily_scanner.py` — multi-strategie depuis 2026-03-02.

Architecture :
- `evaluate_signal()` (RSI2), `evaluate_ibs_signal()` (IBS), `evaluate_tom_signal()` (TOM) — fonctions pures, testables
- Signaux : BUY / SELL / SAFETY_EXIT / HOLD / NO_SIGNAL / PENDING_VALID / PENDING_EXPIRED / WATCH
- Paper trading auto : BUY → `db.open_paper_position()`, SELL → `db.close_paper_position()` avec PnL
- Tables DB : `paper_positions` (open/closed), `signal_log` (audit trail)
- `config/production_params.yaml` — 3 strategies, $5k capital, position_fraction=1.0
- `logs/scanner.log` — log rotatif debug (loguru, 1 MB, 30 jours)

Strategies evaluees :
- RSI(2) : 9 universe + 3 watchlist — entry RSI<10 + close>SMA200*1.01, exit close>SMA5
- IBS : 11 universe + 2 watchlist — entry IBS<0.2 + close>SMA200, exit IBS>0.8 ou close>high_yesterday
- TOM : 17 universe — entry last 5 trading days, exit 3rd day of new month

Paper trading :
- Capital $5,000, position_fraction=1.0 (tout le capital par trade)
- Positions independantes par (strategy, symbol) — RSI2+IBS sur META = 2 positions
- PnL = (exit - entry) * shares (pas de fees en paper)
- Pas de compounding — trade toujours sur capital initial

Workflow :
1. Lancer scanner apres cloture US (~22h CET)
2. BUY → position paper ouverte automatiquement dans la DB
3. SELL/SAFETY_EXIT → position fermee automatiquement, PnL calcule
4. Dashboard multi-strategie + Telegram notification

Coherence anti-look-ahead :
- Entry : signal sur today (= backtest [i-1]), action demain au open (= [i])
- Exit : evalue sur today's close, execute au open suivant (slippage documente, intentionnel)

## Phase 3a -- Deploiement Docker + Telegram (COMPLETE)

Conteneurisation et automatisation du scanner quotidien.

Architecture :
- `engine/notifier.py` — `send_telegram()` (urllib stdlib) + `format_signal_message()` + `format_weekly_summary()`
  - ⚠️ `r.notes` contient `<` et `>` (ex. "RSI=7.4 < 10.0") → toujours `html.escape(r.notes)` avec `parse_mode="HTML"`
- `Dockerfile` — python:3.12-slim + uv + cron ; `ENTRYPOINT ["/entrypoint.sh"]` + `CMD []`
- `docker-compose.yml` — 2 services : scanner (cron) + api (uvicorn :8000, data:ro)
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

## Phase 3b -- Backtesting Framework (COMPLETE)

Framework modulaire : strategies pluggables, moteur unique, pipeline de validation.

Architecture :

- `strategies/base.py` -- BaseStrategy ABC : check_entry(), check_exit(), init_state(), warmup(), param_grid()
- `engine/types.py` -- Direction, ExitSignal, Position, TradeResult, BacktestResult
- `engine/simulator.py` -- Moteur unique generique, remplace fast_backtest + mean_reversion_backtest
  - start_idx/end_idx pour IS/OOS slicing sans reconstruction de cache
  - Gap SL, intraday SL, cooldown, DD guard, force-close
- `validation/pipeline.py` -- validate(strategy, config) -> ValidationReport
  - Robustesse parametrique (48 combos cartesien)
  - Stabilite sous-periodes OOS
  - T-test significativite (one-tailed)
  - Verdict automatique : VALIDATED / CONDITIONAL / REJECTED

Strategies migrees :

- `strategies/rsi2_mean_reversion.py` -- RSI(2) Connors (19 tests)
- `strategies/donchian_trend.py` -- Donchian trend following (27 tests)

Migration verifiee :

- 534 trades sur 4 stocks, PnL identique a $0.0000 (scripts/verify_migration.py)
- 177 tests passent

## Infra Scale-Up (COMPLETE)

Univers YAML, screening batch, resultats structures, CLI compare.

Architecture :

- `config/universes/*.yaml` -- Univers d'assets (us_stocks_large: ~45, us_etfs_broad: 10, us_etfs_sector: 11, forex_majors: 7)
- `config/universe_loader.py` -- `load_universe(name)` -> UniverseConfig, `list_universes()` -> list[str]
- `validation/report.py` -- `save_report(report)` -> JSON dans validation_results/
- `cli/validate.py` -- Refactorise : `python -m cli.validate <strategy> <universe>` (argparse + YAML)
- `cli/screen.py` -- Screening rapide : backtest simple sur tout un univers, trie par PF
- `cli/compare.py` -- Tableau croise de tous les resultats JSON

Nouveaux fee models :

- `FEE_MODEL_FOREX_SAXO` : spread 0.015%, pas de commission (Saxo forex)

CLI usage :

```bash
python -m cli.validate rsi2 us_stocks_large           # validation complete
python -m cli.validate rsi2 us_stocks_large --capital 100000 --no-whole-shares
python -m cli.screen rsi2 us_stocks_large              # screen rapide (pas de robustesse)
python -m cli.compare                                   # compare les JSON sauvegardes
python -m cli.validate --list-universes                # lister les univers
python -m cli.validate --list-strategies               # lister les strategies
```

## SQLite Unified DB (COMPLETE)

Migration de l'architecture duale (Parquet + SQLite resultats) vers une base SQLite unique.

Architecture :

- `data/db.py` -- `SignalRadarDB` : base unique `data/signal_radar.db`
  - Table `ohlcv` : prix OHLCV de tous les assets (PRIMARY KEY symbol+date)
  - Tables `screens`, `validations`, `pooled_results` : resultats d'analyse
  - `get_ohlcv()` retourne Adj_Close = Close (donnees deja ajustees)
- `data/yahoo_loader.py` -- Modifie : ecrit/lit depuis DB au lieu de parquet
- `cli/data.py` -- Gestion donnees via SignalRadarDB (plus de CacheManager)
- `cli/analyze.py` -- Analyse resultats via SignalRadarDB (plus de ResultsDB)

Fichiers supprimes :

- `data/cache_manager.py` -- remplace par data/db.py
- `validation/results_db.py` -- fusionne dans data/db.py
- `data/cache/*.parquet` -- donnees migrees dans SQLite
- `validation_results/results.db` -- remplace par data/signal_radar.db

## Phase 4a -- FastAPI Dashboard API (COMPLETE)

API REST read-only pour alimenter un futur frontend React. Le scanner reste le seul writer.

Architecture :

- `api/app.py` -- FastAPI app (CORS, lifespan), GET-only
- `api/config.py` -- DB_PATH + load_production_config()
- `api/dependencies.py` -- get_db() singleton (overridable en test)
- `api/routes/signals.py` -- /api/signals/today, /history
- `api/routes/positions.py` -- /api/positions/open, /closed
- `api/routes/performance.py` -- /api/performance/summary, /equity-curve
- `api/routes/market.py` -- /api/market/overview (tous les assets + indicateurs actuels)
- `api/routes/backtest.py` -- /api/backtest/screens, /validations, /compare

Nouvelles methodes DB (data/db.py) :

- `get_latest_signals(strategy=None)` -- (timestamp, signaux) du dernier run
- `get_signal_history(strategy, symbol, signal_type, days)` -- historique N jours
- `get_latest_price(symbol)` -- dernier close_price depuis signal_log
- `get_latest_prices(symbols)` -- batch version
- `get_screens_filtered(strategy, universe, min_pf)` -- screens tries par PF
- `get_validations_filtered(strategy, universe, verdict)` -- validations filtrees

Notes :

- Prix latent = close_price du signal_log (pas de fetch Yahoo live)
- market/overview lit production_params.yaml pour mapping universe/watchlist
- TestClient + dependency override (get_db) pour tests isoles
- 311 tests (280 existants + 8 DB + 13 API)
- get_screens_filtered() + get_validations_filtered() : dedupliques (MAX timestamp par strategy+universe+symbol)
- Noms strategies DB : screens=court (rsi2/ibs/tom), validations=long (rsi2_mean_reversion/ibs_mean_reversion/turn_of_month)

## Phase 4b -- React Frontend Dashboard (COMPLETE)

Frontend read-only consommant l'API FastAPI. Outil d'aide a la decision consulte apres cloture US.

Architecture :

- `frontend/` -- Vite + React 18 + Tailwind CSS v4 + Recharts + React Router
- `frontend/src/api/client.js` -- 11 fonctions fetch -> endpoints FastAPI
- `frontend/src/hooks/useApi.js` -- Hook custom (loading/error/refetch, pas de polling)
- `frontend/src/hooks/useRefresh.jsx` -- RefreshContext (bouton Refresh global)
- `frontend/src/utils/format.js` -- Formatage + constantes couleurs (STRATEGY_COLORS, SIGNAL_COLORS, VERDICT_COLORS)
- `frontend/src/pages/Dashboard.jsx` -- KPIs + signaux + positions + equity curve + market overview
- `frontend/src/pages/Backtest.jsx` -- Compare Matrix + Validations + Screens (sub-tabs)

Composants principaux :

- `components/performance/StrategyBreakdown.jsx` -- 5 KPI cards + breakdown par strategie
- `components/signals/StrategySection.jsx` + `SignalCard.jsx` -- Signaux par strategie (BUY/SELL/HOLD/WATCH)
- `components/positions/OpenPositions.jsx` + `ClosedTrades.jsx` -- Tables positions + trades
- `components/performance/EquityCurve.jsx` -- Recharts AreaChart PnL cumule
- `components/market/MarketOverview.jsx` -- Grille assets multi-strategie
- `components/backtest/CompareMatrix.jsx` -- Matrice strategie x asset avec verdicts
- `components/backtest/ValidationsTable.jsx` + `ScreensTable.jsx` -- Tables filtrables

Design system :

- Theme dark : bg-primary #0f1117, bg-card #1a1d27
- Strategies : RSI2=blue, IBS=purple, TOM=amber
- Signaux : BUY=green, SELL=red, HOLD=blue, WATCH=amber
- Typo : JetBrains Mono (donnees) + Space Grotesk (titres)
- Refresh manuel (pas de polling) -- scanner 1x/jour

Port dev : 3001 (ports 4654-5805 exclus par Hyper-V sur cette machine)

Note : 313 tests Python (311 + 2 dedup tests DB).

## Phase 4c -- Docker Packaging Scanner + API + Frontend (COMPLETE)

Ajout service `api` dans Docker Compose. Le dashboard est accessible depuis le LAN apres deploiement.

Architecture :

```
docker-compose.yml
  scanner  -- cron 22:15, seul writer de la DB
  api      -- uvicorn :8000, lit la DB en :ro, sert frontend/dist/ en static
  └── shared volume ./data (SQLite)
```

Fichiers cles :

- `Dockerfile.api` -- multi-stage build : stage 1 Node.js build frontend, stage 2 Python API
  - Stage 1 `node:20-slim` : npm ci + npm run build -> frontend/dist/
  - Stage 2 `python:3.12-slim` : fastapi + uvicorn + pandas + pyyaml + COPY dist/ depuis stage 1
  - Pas de cron, pas de numpy/yfinance/pyarrow ; Node.js absent de l'image finale
- `requirements-api.txt` -- deps API uniquement
- `api/app.py` -- mount `StaticFiles(directory=frontend/dist, html=True)` APRES les routes API
  - `html=True` : renvoie index.html pour les routes SPA (/backtest etc.)
  - `if FRONTEND_DIR.is_dir()` : conditionnel -> tests et dev local non impactes
- `Dockerfile` -- bug corrige : ajout `data/db.py` manquant (scanner l'importe)
- `docker-compose.yml` -- service `api` : ports 9000:8000, data:ro, config:ro

Notes :

- SQLite journal mode DELETE (defaut) : compatible avec volume :ro pour l'API
  WAL ne marcherait PAS en :ro (les lecteurs ecrivent dans -wal/-shm)
- Multi-stage build : Node.js absent de l'image finale, Node.js PAS requis sur le serveur
  `docker compose build` seul suffit (le build frontend est encapsule dans le Dockerfile.api)
- Premier deploiement : lancer `docker compose exec scanner python scripts/daily_scanner.py` pour creer la DB

Deploiement :

```bash
bash deploy/deploy.sh
# -> git pull + docker compose build (inclut npm build) + up -d
# -> Dashboard : http://192.168.1.200:9000
```

## Phase 4d -- CLI Container + Scanner Trigger + Live Trades (COMPLETE)

Trois ameliorations au systeme deploye.

### 1. CLI dans le container scanner

`Dockerfile` inclut desormais `strategies/`, `validation/`, `cli/` -> les commandes CLI fonctionnent dans le container :

```bash
docker compose exec scanner python -m cli.screen rsi2 us_stocks_large
docker compose exec scanner python -m cli.validate --list-strategies
```

### 2. Bouton "Run Scanner" dans le dashboard

Architecture : l'API execute le scanner en subprocess (code scanner copie dans l'image API).

- `api/routes/scanner.py` -- `POST /api/scanner/run` (subprocess asyncio, 5 min timeout, lock anti-concurrent) + `GET /api/scanner/status`
- `Dockerfile.api` -- ajout `engine/`, `strategies/`, `data/base_loader.py`, `data/yahoo_loader.py`, `scripts/`
- `requirements-api.txt` -- ajout `numpy`, `yfinance`, `loguru` pour le scanner
- `docker-compose.yml` -- `data/` passe en rw (scanner ecrit depuis le container API) + `env_file: .env` pour Telegram
- Frontend : bouton "Scan" dans la Navbar (vert, spinner, feedback OK/error, refresh auto si succes)

Notes :

- SQLite : un seul writer a la fois, le second attend (mode DELETE, timeout 30s)
- `data/` rw pour l'API : l'API n'est plus 100% read-only (acceptable projet solo LAN)

### 3. Live Trades -- logging des trades reels

Table `live_trades` dans la DB + API CRUD + composants React.

DB (`data/db.py`) :

- Table `live_trades` : strategy, symbol, entry_date, entry_price, shares, fees_entry/exit, pnl, paper_position_id
- `UNIQUE(strategy, symbol, entry_date)` -- anti-doublon
- Methodes : `open_live_trade`, `close_live_trade`, `get_open_live_trades`, `get_closed_live_trades`, `get_live_summary`
- PnL inclut fees : `(exit - entry) * shares - fees_entry - fees_exit`

API (`api/routes/live.py`) :

- `POST /api/live/open` -- ouvrir un trade (409 si doublon)
- `POST /api/live/close` -- fermer un trade (404 si absent)
- `GET /api/live/open` -- positions ouvertes + unrealized PnL (depuis signal_log)
- `GET /api/live/closed` -- trades fermes
- `GET /api/live/summary` -- resume live (n_trades, win_rate, total_pnl, by_strategy)
- `GET /api/live/compare` -- paper vs live cote a cote

Frontend :

- `components/live/LiveTradeForm.jsx` -- modal open/close trade (pré-rempli depuis paper position)
- `components/live/LivePositions.jsx` -- tableau trades live ouverts avec bouton Close
- `components/live/PaperVsLive.jsx` -- cards comparaison paper vs live (masque si vide)
- `components/positions/OpenPositions.jsx` -- bouton "Log Real" par ligne (pré-remplit le formulaire)
- `pages/Dashboard.jsx` -- LivePositions + PaperVsLive integres

348 tests (313 + 8 TestLiveTrades DB + 1 TestScanner API + 7 TestLive API + 19 hardening audit).

## Hardening Audit (COMPLETE)

Audit securite, integrite, performance, et qualite du code. 348 tests.

### Securite

- CORS restreint : `allow_origins` limite a localhost:3001 + LAN 192.168.1.200:9000 (plus de wildcard `*`)
- Validation d'inputs API : `Query(gt=0)` sur entry_price, shares, exit_price ; `Query(ge=0)` sur fees ; `Query(ge=1, le=1000)` sur limit
- CHECK constraints DB : `entry_price > 0`, `shares > 0`, `fees >= 0` sur paper_positions et live_trades
- `sys.executable` dans scanner subprocess (plus de `["python", ...]`)

### Integrite des donnees

- TOCTOU fix : `open_paper_position` et `close_paper_position` utilisent `BEGIN EXCLUSIVE` (atomique)
- `pnl_pct` net : calcul corrige `pnl_dollars / cost_basis * 100` (inclut fees, coherent avec pnl_dollars)
- `get_latest_prices()` : requete batch `WHERE symbol IN (...)` (plus de N queries individuelles)

### Performance

- SQLite timeout=30s : toutes connexions via `self._connect()` (evite OperationalError instantanee)
- Indexes : `signal_log(timestamp)`, `signal_log(symbol, timestamp)`, `paper_positions(status, strategy)`, `live_trades(status, strategy)`
- N+1 fix : `positions.py` et `performance.py` utilisent `get_latest_prices()` batch
- Aggregations SQL : `get_paper_summary()` et `get_live_summary()` utilisent `SUM`/`COUNT` SQL (plus de boucles Python)

### Fiabilite

- Scanner lock : `asyncio.Lock` remplace le booleen `_scan_running` (thread-safe)
- Config error handling : `load_production_config()` avec cache + try/except (FileNotFoundError, YAMLError)
- HEALTHCHECK Docker dans `Dockerfile.api`

### Code quality

- `t_stat` backtest API : retourne `None` au lieu du p-value (le t-stat n'est pas stocke dans validations)
- Notifier : supprime hardcode `RSI(2)=` dans `format_signal_message()` (utilise `r.notes` generique)
- Deps prod : retire `pyarrow` (inutilise) et `pytest` (dev-only) de requirements.txt, ajoute `scipy`

### Tests ajoutes (+19)

- TestInputValidation (10 tests) : prix negatifs, shares=0, fees negatifs, limit invalide
- TestLiveTrades edge cases (7 tests) : loss, breakeven, zero fees, pnl_pct net, batch prices
- Total : 329 -> 348 tests

## Backtest Audit (COMPLETE)

Audit systematique du moteur de backtest (simulator.py, strategies/, indicators.py).
Objectif : identifier les biais communs (look-ahead, execution, annualisation).

### Resultats de l'audit

1. **RSI2 SMA exit : pas de look-ahead circulaire** (prouve algebriquement)
   - `close[i] > SMA5[i]` se reduit a `close[i] > mean(close[i-4:i])`
   - L'auto-reference de close[i] dans SMA5 s'annule : 5*C > C+sum(prev4) ⟺ 4*C > sum(prev4)
   - Le signal RSI2 est mathematiquement propre. Seul l'execution timing (close vs next open) est une approximation, symetrique et non biaisee.

2. **IBS exit : biais inverse a l'hypothese** (mesure empiriquement)
   - Hypothese initiale : IBS > 0.8 (close pres du high) = exit optimiste, open[i+1] serait plus bas
   - Resultat mesure (`scripts/compare_ibs_exit_timing.py`) : open[i+1] est PLUS HAUT en moyenne
   - PF moyen : 1.53 (close) → 1.68 (open[i+1]) = +9.4%. PnL total : +37.1%
   - Cause : premium overnight sur clotures fortes (Lou, Polk & Skouras 2019)
   - Conclusion : le backtest IBS est CONSERVATEUR, pas optimiste

3. **TOM exit : pas de biais** — date de sortie calendaire connue d'avance

4. **Sharpe annualise corrige** — ancien calcul sqrt(252) sur per-trade returns surestimait ~5x
   - Nouveau calcul : `sqrt(trades_per_year)` base sur la duree reelle couverte
   - Impact : affichage uniquement, aucun impact sur les verdicts (PF/robustesse/t-test)

### IBS exit timing -- resultats detailles

OOS 2014-2025, $10k whole shares, fee_model=us_stocks_usd_account :

| Ticker | Trades | PF close | PF open[i+1] | Delta |
| ------ | ------ | -------- | ------------ | ----- |
| META   | 331    | 1.72     | 1.93         | +12.5%|
| MSFT   | 325    | 1.53     | 1.73         | +13.7%|
| GOOGL  | 300    | 1.29     | 1.41         | +9.0% |
| NVDA   | 332    | 1.86     | 2.08         | +12.0%|
| AMZN   | 296    | 1.41     | 1.45         | +2.7% |
| AAPL   | 301    | 1.40     | 1.46         | +4.4% |

Delta positif sur les 6 assets sans exception. Pas d'outlier dominant.
Breakdown : ibs_exit +$2.69/trade, prev_high_exit +$5.93/trade, trend_break +$1.46/trade.

### Conventions backtest confirmees

- Entry anti-look-ahead : signal sur [i-1], action sur open[i] -- CORRECT
- Exit close-based MR : signal sur close[i], exit a close[i] -- CONSERVATEUR (mesure)
- Gap-aware SL : check open vs SL avant intraday -- CORRECT
- Force-close exclu des resultats -- CORRECT
- Fee model complet (commission + spread + FX + overnight) -- CORRECT
- Entry fee non double-comptee -- CORRECT (bug Phase 1 corrige)

## Proximity Alerts (COMPLETE)

Section "Approaching Trigger" dans le dashboard : anticiper les BUY avant qu'ils triggent.

### Implementation

- `signal_log` : colonne `details_json TEXT` ajoutee (migration `ALTER TABLE ADD COLUMN`, safe)
  - Stocke tous les indicateurs bruts du scan (RSI, SMA200, IBS, trend_ok, etc.) en JSON
  - Migration : anciens signaux ont `details_json = NULL`, proximite calculee des le prochain scan
  - `log_signal()` : nouveau parametre `details_json: str | None = None` (backward-compatible)
- `scripts/daily_scanner.py` : `result.details` serialise en JSON dans chaque `log_signal()`
  - `evaluate_signal()` : ajoute `trend_ok` dans details (close > sma200*buffer)
  - `evaluate_ibs_signal()` : ajoute `trend_ok` dans details (close > sma200)
  - `evaluate_tom_signal()` : ajoute `entry_days_before_eom` dans details (pour calcul cote API)
- `api/routes/market.py` : `_compute_proximity()` calcule la proximite depuis `details_json`
  - RSI2 : near zone = threshold x 2 (< 20), pct 0->100 vers le seuil, bloquee si trend_ok=False
  - IBS : near zone = threshold x 2 (< 0.4), idem
  - TOM : near zone = entry_window + 3 jours, pct 0->100 vers la fenetre d'entree
  - `proximity` = null pour BUY/HOLD/SELL ; champ ajoute a chaque strategie de `/api/market/overview`
- `frontend/src/components/signals/NearTrigger.jsx` : section "Approaching Trigger"
  - Cards horizontales scrollables triees par pct decroissant
  - S'affiche seulement si au moins un asset a `proximity.near = true`
  - Indicateur trend : point vert/rouge, card grisee si trend bloque
- `frontend/src/components/market/MarketOverview.jsx` : `ProximityBar` sous les cellules
  - Barre + label compact (ex: "RSI=13.5 / 10") quand `proximity.near = true`
  - Couleur : vert si pct >= 75, ambre si >= 50, gris sinon

### Tests ajoutes (+10)

- TestDetailsJson (4 tests DB) : stockage/lecture details_json, NULL backward-compat, signal_history
- TestDetailsTrendOk (4 tests scanner) : trend_ok vrai/faux pour RSI2 et IBS
- TestMarketProximity (2 tests API) : NO_SIGNAL a proximity != null, BUY n'en a pas
- Total : 348 -> 358 tests

## Monthly Refresh (COMPLETE)

Refresh automatique mensuel des screens et validations. Garde le dashboard a jour quand les donnees de marche evoluent.

### Implementation

- `cli/runner.py` -- Source unique STRATEGIES/FEE_MODELS/MARKET_DEFAULTS + fonctions importables
  - `run_screen(strategy_key, universe_name, *, capital, whole_shares, fee_model_name, is_end, data_end, db)` -> ScreenResult
  - `run_validate(strategy_key, universe_name, *, ..., save_json, db)` -> ValidateResult
  - `resolve_market_params(universe_config, ...)` -> (capital, whole_shares, fee_model, name)
  - `_merge_grid_with_defaults(strategy)` -- copie locale (validation/pipeline.py garde la sienne)
  - `data_end=None` -> `datetime.now()` (dynamique). CLI gardent `--data-end 2025-01-01` pour backward compat
  - cli/screen.py et cli/validate.py deviennent des wrappers argparse (~80 lignes chacun)
- `scripts/monthly_refresh.py` -- Orchestrateur du refresh mensuel [PRODUCTION]
  - `DEFAULT_COMBOS` : 9 combos (rsi2/ibs/tom x us_stocks_large/us_etfs_broad/us_etfs_sector)
  - Exclus : forex_majors (REJECTED), donchian (REJECTED sur tous les univers)
  - `run_refresh(combos, mode, dry_run)` -> RefreshSummary (isolement erreurs par combo)
  - `_snapshot_validations(db)` + `_compute_verdict_changes(before, after)` -> diff verdicts
  - `format_refresh_telegram(summary)` -> message HTML Telegram
  - `--mode screen` (defaut, ~45min) ou `--mode validate` (~6.5h)
  - `--dry-run`, `--combos rsi2:us_etfs_broad` pour execution partielle
- `deploy/crontab` -- cron mensuel ajout : 1er du mois a 04:00 (hors conflit scanner 22:15)

### Commandes refresh

```bash
python scripts/monthly_refresh.py --dry-run           # liste les 9 combos
python scripts/monthly_refresh.py                      # screen mode (~45 min)
python scripts/monthly_refresh.py --mode validate      # validation complete (~6.5h)
python scripts/monthly_refresh.py --combos rsi2:us_etfs_broad  # un seul combo
docker compose exec scanner python scripts/monthly_refresh.py --dry-run
```

### Tests ajoutes (+39)

- TestConstants/TestResolveMarketParams/TestMergeGridWithDefaults (13 tests cli/runner) : constantes + utilitaires
- TestRunScreenValidation (8 tests cli/runner) : importabilite + erreurs input
- TestVerdictChanges (7 tests) : upgrade/downgrade/new/removed/multiple/empty
- TestTelegramFormat (5 tests) : screen/validate/failures/changes/HTML escape
- TestDefaultCombos (5 tests) : strategies valides, univers valides, count, no-forex, no-donchian
- TestSnapshotValidations (1 test) : DB vide -> snapshot vide
- Total : 358 -> 397 tests

## Trade Journal (COMPLETE)

Page /journal dans le dashboard : timeline unifiee des trades paper et live, avec contexte signal, comparaison slippage, et notes editables.

### Fichiers crees/modifies

- `data/db.py` : migration `paper_positions.notes` (ALTER TABLE safe) + 3 methodes publiques :
  - `update_paper_notes(position_id, notes)` -> bool
  - `update_live_notes(trade_id, notes)` -> bool
  - `get_journal_entries(strategy, symbol, source, search, limit, offset)` -> dict
  - helpers prives `_holding_days`, `_attach_signal_context` (batch, fenetre 4j), `_attach_slippage`
- `api/routes/journal.py` : 3 endpoints (GET /entries, PATCH /paper/{id}/notes, PATCH /live/{id}/notes)
- `api/app.py` : router journal + PATCH ajoute dans allow_methods CORS
- `frontend/src/api/client.js` : `patchJson()` + `journalEntries`, `journalPaperNote`, `journalLiveNote`
- `frontend/src/pages/Journal.jsx` : page principale, timeline groupee par date
- `frontend/src/components/journal/` :
  - `JournalFilters.jsx` -- dropdowns strategie/symbol/source + search (debounce 300ms)
  - `JournalStats.jsx` -- total/WR/PnL/avg-hold (depuis stats API)
  - `TradeCard.jsx` -- card par trade : badge PAPER/LIVE, signal context formate, slippage, notes
  - `NoteEditor.jsx` -- editeur inline (click Edit -> textarea -> Save/Cancel)

### Schema retourne par get_journal_entries

- `source` : "paper" ou "live"
- `holding_days` : jours calendaires (pas trading days -- intentionnel pour mesurer immobilisation capital)
- `signal_details` : dict depuis `signal_log.details_json`, null si pas de signal dans les 4j suivant l'entree
- `slippage` : {entry_diff, exit_diff, pnl_diff} pour les live trades avec `paper_position_id`, null sinon
- Tri : open d'abord, puis par entry_date desc
- Stats aggregees sur l'ensemble filtre (avant pagination)

### Tests ajoutes (+11)

- TestJournal DB (6 tests) : update_paper/live notes, nonexistent, entries empty, entries mixed
- TestJournal API (5 tests) : entries ok, with trades, patch notes, nonexistent, filter strategy
- Total : 422 -> 433 tests

## Dashboard Polish (COMPLETE)

4 ameliorations UX groupees : Win Rate ring, auto-refresh, mobile responsive, Telegram daily summary.

### Frontend

- `frontend/src/components/performance/StrategyBreakdown.jsx` : Win Rate card -- `isRing: n_closed_trades > 0` (affiche "--" si 0 trades fermes, plus d'anneau rouge vide trompeur)
- `frontend/src/hooks/useRefresh.jsx` : auto-refresh toutes les 5 minutes via `setInterval` (tous les composants se rafraichissent automatiquement apres le scan)
- `frontend/src/components/layout/Navbar.jsx` : responsive mobile -- `flex-wrap`, `min-h-12`, gap reduit sur mobile, "Last scan" cache sur petit ecran (`hidden sm:inline`), logo `shrink-0`

Note : toutes les tables avaient deja `overflow-x-auto` et les signal cards avaient deja un grid responsive. Seule la Navbar necessitait un ajustement.

### Backend Telegram

- `engine/notifier.py` : `format_daily_summary()` -- message complet envoye TOUS les jours (plus de silence les jours sans signal). Contenu : header scan + signaux BUY/SELL + positions ouvertes avec unrealized PnL + paper stats + approaching triggers (top 5). Jamais None.
- `scripts/daily_scanner.py` : `_extract_approaching()` -- extrait les assets proches du trigger depuis `all_results` (logique identique a `_compute_proximity()` dans market.py). `main()` appelle `format_daily_summary()` au lieu de `_format_telegram_message()` (supprimee).

### Nouveaux tests (+10)

- TestFormatDailySummary (6 tests) : always returns string, no signals, BUY signal, open positions unrealized PnL, approaching, paper stats header
- TestExtractApproaching (4 tests) : RSI near trigger, trend blocked, BUY excluded, IBS near trigger
- Total : 433 -> 443 tests
