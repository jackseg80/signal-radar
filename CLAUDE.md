# CLAUDE.md — signal-radar

## Project Status
Phase 1 COMPLETE -- Phase 2 COMPLETE -- Phase 3 COMPLETE -- Infra Scale-Up COMPLETE -- SQLite Unified DB COMPLETE -- Multi-Strategy Scanner COMPLETE -- FastAPI Dashboard API COMPLETE -- React Frontend Dashboard COMPLETE.
Framework backtest modulaire operationnel. 313 tests.
Validated strategies : RSI(2) MR (10 stocks), IBS MR (13 stocks), TOM (21 stocks + 6 ETFs).
Base SQLite unique (data/signal_radar.db) : prix OHLCV + resultats + paper trading.
Scanner multi-strategie avec paper trading ($5k capital).
API REST read-only (FastAPI) + Frontend React (Vite + Tailwind v4 + Recharts).

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
- Docker logs : `docker compose logs -f scanner`
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
  db.py                                -- SignalRadarDB : base SQLite unique (prix OHLCV + resultats + paper trading)
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
  test_notifier.py                     -- Tests notifier Telegram
  test_data_loader.py                  -- Tests YahooLoader validation
  test_db.py                           -- Tests SignalRadarDB + paper trading + API methods (35 tests)
  test_api.py                          -- Tests FastAPI endpoints (13 tests)
  conftest.py                          -- Fixtures partagees

scripts/
  daily_scanner.py                     -- Scanner multi-strategie RSI2+IBS+TOM + paper trading [PRODUCTION]
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

api/                                   -- FastAPI Dashboard API (read-only)
  app.py                               -- FastAPI app, CORS, lifespan, routes
  config.py                            -- Settings (DB_PATH, load_production_config)
  dependencies.py                      -- get_db() singleton
  routes/
    signals.py                         -- GET /api/signals/today, /history
    positions.py                       -- GET /api/positions/open, /closed
    performance.py                     -- GET /api/performance/summary, /equity-curve
    market.py                          -- GET /api/market/overview
    backtest.py                        -- GET /api/backtest/screens, /validations, /compare

deploy/
  entrypoint.sh                        -- Ecrit env vars cron + passthrough CMD
  crontab                              -- 22h15 dim-ven (TZ=Europe/Zurich)
  deploy.sh                            -- Script deploiement serveur Ubuntu
  README.md                            -- Instructions deploiement serveur

docs/
  PHASE1_RESULTS.md                    -- Resultats complets Phase 1
  PHASE2_STOCKS_RESULTS.md             -- Resultats Steps 11-13
  PHASE2_RESULTS.md                    -- Phase 2 complete
  ROADMAP.md                           -- Roadmap Phase 1-5
```

## Conventions techniques

- Anti-look-ahead : signal sur [i-1], action sur open[i]
- Gap-aware exits : verifier open vs SL avant le intraday
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
