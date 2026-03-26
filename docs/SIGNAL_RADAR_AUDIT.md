# Signal Radar — Architecture Audit

*Dernière mise à jour : Mars 2026*

---

## Vue d'ensemble

Signal Radar est une plateforme de trading quantitative US stocks/ETFs spécialisée en Mean Reversion et stratégies saisonnières. Elle offre un backtesting modulaire, un scanner quotidien automatisé, et un dashboard web.

| Métrique | Valeur |
|----------|--------|
| Stratégies validées | 3 (RSI2, IBS, TOM) |
| Univers production | 6 actions + 5 ETFs |
| Période OOS | 2014–2025 |
| Tests | 457 unitaires |
| Stack | Python 3.12 + FastAPI + React |

---

## Architecture globale

```
signal-radar/
├── strategies/           -- Plugins stratégie (RSI2, IBS, TOM, Donchian)
├── engine/               -- Moteur simulation + indicateurs + cache
├── validation/           -- Pipeline robustesse + stats
├── optimization/         -- Détection overfitting (Monte Carlo, DSR)
├── data/                 -- SQLite DB + Yahoo Finance loader
├── api/                  -- FastAPI REST (signaux, positions, perf, journal)
├── frontend/             -- React dashboard (Vite + Tailwind v4 + Recharts)
├── scripts/              -- Scanner quotidien + monthly refresh
├── cli/                  -- Commandes screen/validate/analyze
└── config/               -- Univers YAML + params production
```

---

## 1. Stratégies — Pattern BaseStrategy ABC

**Fichier** : `strategies/base.py` (126 lignes)

### Contrat d'interface

```
check_entry(i)    → Direction (FLAT/LONG/SHORT) sur candle [i-1], entrée sur open[i]
check_exit(i)      → ExitSignal | None (après gap SL + intraday SL moteur)
init_state()       → dict d'état initial (vide par défaut, override pour trailing/etc.)
warmup(params)     → nombre de candles warmup (default: max(periods) + 10)
param_grid()       → grille de paramètres pour robustesse + cache indicateurs
default_params()   → params canoniques (Connors, non optimisés)
```

### Implémentations

| Stratégie | Fichier | Type signal | Validated |
|-----------|---------|-------------|-----------|
| RSI(2) MR | `strategies/rsi2_mean_reversion.py` | Technique (RSI<10) | ✅ 4 stocks |
| IBS MR | `strategies/ibs_mean_reversion.py` | Technique (IBS<0.2) | ✅ 6 stocks + QQQ |
| TOM | `strategies/turn_of_month.py` | Calendaire | ✅ 4 stocks + 3 ETFs |
| Donchian TF | `strategies/donchian_trend.py` | Technique | ❌ Rejeté (forex) |

### Points forts
- Interface minimale (5 méthodes) — chaque stratégie = 1 fichier
- Pas de multi-TF, pas de `StrategyContext` complexe
- `IndicatorCache` passé en paramètre — pas d'accès direct aux prix

### Points à améliorer
- **Pas de registry automatique** — les stratégies sont importées manuellement dans `cli/validate.py` et `cli/screen.py`. Ajouter une stratégie nécessite de modifier 2 fichiers CLI.
- **Pas de `check_exit` strategy-specific séparé** — le gap SL et intraday SL sont gérés par le moteur, mais certaines stratégies (trailing stop) ont besoin d'un exit intermédiaire qui n'est pas encore implémenté proprement.

---

## 2. Moteur de simulation

**Fichier** : `engine/simulator.py` (363 lignes)

### Architecture — Moteur unique

Un seul `simulate(strategy, cache, params, config)` remplace les 2 anciens moteurs (trend + MR). Gère :

| Fonction | Détail |
|----------|--------|
| Sizing | `whole_shares` (floor) ou `fractional` |
| Fee model | Entry + exit + overnight costs |
| Gap-aware SL | Gap past SL → exit at open (pas au SL) |
| Intraday SL | Check H/L vs SL price avec slippage |
| Strategy exit | Via `ExitSignal(price, reason, apply_slippage)` |
| Same-candle exit | Entry + exit possible sur même bougie |
| Cooldown | Après sortie |
| DD guard | Max drawdown → stop |

### Timing anti-look-ahead

```
Signal entry : close[i-1]   →  Entry : open[i]
Signal exit  : close[i-1]   →  Exit  : open[i]
```

### Points forts
- **Moteur unique** — pas de duplication, maintenable
- **Gap SL** — gère correctement les gaps overnight
- **Fee model intégré** — pas de double-comptage (entry_fee corrigé Phase 1)
- **Anti-look-ahead strict** — signal sur [i-1], action sur open[i]

### Points à améliorer
- **Pas de support multi-position** — chaque stratégie = 1 position max (OK pour daily, limitant pour grid)
- **Pas de trailing stop natif** — `Position.state` permet de stocker un HWM, mais le check est à la charge de la stratégie

---

## 3. Cache indicateurs

**Fichier** : `engine/indicator_cache.py`

```python
build_cache(arrays, cache_grid, dates=None)
```

Pré-calcule tous les indicateurs pour toutes les variantes de paramètres du grid. Le même cache est réutilisé pour chaque combo → speedup important pour la robustesse.

Indicateurs supportés : SMA, EMA, RSI (Wilder), ATR, Donchian, IBS, ADX, BB, Supertrend + tableaux calendaires (`trading_day_of_month`, `trading_days_left_in_month`).

---

## 4. Pipeline de validation

**Fichier** : `validation/pipeline.py` (173 lignes)

### 10 étapes

```
1. Charger données (YahooLoader)
2. Trouver indices OOS (is_end → OOS start)
3. Build cache (merged param_grid + defaults)
4. BacktestConfig par asset
5. OOS backtest (params canoniques)
6. Robustesse paramétrique (48 combos)
7. Sous-périodes (OOS-A / OOS-B)
8. T-test
9. Verdict
10. T-test poolé
```

### Critères de validation

| Critère | Seuil minimum | Seuil solide |
|---------|--------------|--------------|
| Profit Factor | > 1.4 | > 1.6 |
| Win Rate | > 60% | > 65% |
| Robustesse param. | > 80% combos + | 100% |
| Sous-périodes | PF > 1.0 les 2 | PF > 1.0 + stable |
| T-test p-value | < 0.05 | < 0.01 |

### Résultats validés OOS 2014-2025

**RSI(2) Mean Reversion** (META, MSFT, GOOGL, NVDA) :
- PF 1.48–3.49, WR 67–74%, 100% robustesse
- T-test poolé : t=4.27, p=0.0000

**IBS Mean Reversion** (META, MSFT, GOOGL, NVDA, AMZN, AAPL) :
- PF 1.29–2.07, WR 63–72%, 100% robustesse
- T-test poolé : t=3.81, p=0.0001

**TOM** (META, NVDA, AAPL, AMZN + SPY, QQQ, DIA) :
- PF 1.23–1.89, WR 53–64%, 100% robustesse
- T-test poolé : t=3.90, p=0.0001

---

## 5. Détection d'overfitting

**Fichier** : `optimization/overfit_detection.py` (380 lignes)

### 4 méthodes implémentées

| Méthode | Description | Usage |
|---------|-------------|-------|
| Monte Carlo block bootstrap | Circular block bootstrap, block=10 jours, 1000 sims | Valide que l'edge n'est pas dû au hasard |
| Deflated Sharpe Ratio | Bailey & Lopez de Prado (2014) | Corrige le Sharpe pour multiple testing |
| Parameter stability | Perturbation ±10%, ±20% | Détecte les params "cliff" |
| Cross-asset convergence | Coefficient de variation des params optimaux | Valide que les params marchent across assets |

### Notes
- Monte Carlo avec `block_size=10` (2 semaines) pour préserver l'autocorrélation
- DSR : `n_trials = nombre de combinaisons testées` (48 pour la robustesse canonique)
- Stabilité paramétrique intégrée au pipeline de robustesse

---

## 6. Base de données SQLite

**Fichier** : `data/db.py` (555 lignes)

### Tables

| Table | Usage | Index |
|-------|-------|-------|
| `ohlcv` | Prix OHLCV daily | `(symbol, date)` PK |
| `validations` | Résultats pipeline validation | strategy/universe/symbol/timestamp |
| `screens` | Résultats screen rapide | strategy/universe/symbol/timestamp |
| `paper_positions` | Positions paper (open/closed) | `(status, strategy)` |
| `live_trades` | Trades live avec fees | `(status, strategy)` |
| `signal_log` | Log signaux quotidien | `(timestamp)`, `(symbol, timestamp)` |
| `asset_metadata` | Names, logos | symbol PK |

### Migrations
- ALTER TABLE avec `try/except` pour colonnes optionnelles ajoutées post-initialisation
- Pas de schema migration tool (migrations manuelles en `_init_db`)

### Points forts
- **ACID compliant** — journalisation et paper trading avec intégrité
- **Unified** — OHLCV + backtests + paper + live dans une seule DB
- **Indexes appropriés** — sur les colonnes de filtre fréquentes

### Points à améliorer
- **Pas de versioning schema** — les migrations sont implicites via try/except
- **Pas de backup/cleanup automatique** — la DB grandit indéfiniment
- **Connection timeout 30s** — OK pour local, might be tight for concurrent API access

---

## 7. API REST FastAPI

**Fichier** : `api/app.py`

### Routes

| Route | Méthodes | Description |
|-------|----------|-------------|
| `/api/signals` | GET | Signaux du jour + historique |
| `/api/positions` | GET | Positions open/closed |
| `/api/performance` | GET | Summary + equity curve |
| `/api/market` | GET | Overview + prix asset |
| `/api/backtest` | GET | Screens, validations, compare, robustness |
| `/api/scanner` | POST/GET | Trigger scanner + status |
| `/api/live` | POST/GET | Open/close trades live |
| `/api/journal` | GET/PATCH | Entries + notes editables |
| `/api/config` | GET | Settings (initial_capital) |

### Points forts
- **CORS ouvert** — GET + POST acceptés
- **SPA mount** — frontend statique servie par FastAPI
- **HEALTHCHECK** — Docker healthcheck sur `/api/health`
- **StaticFiles** — dashboard compilé dans le container API

### Points à améliorer
- **Pas d'authentification** —API ouverte sur le LAN (acceptable pour usage personnel)
- **Pas de rate limiting** — scanner trigger sans throttling
- **Pas de cache** — chaque requête refait des queries DB

---

## 8. Frontend React

**Stack** : React 18 + Vite + Tailwind CSS v4 + Recharts + React Router + Framer Motion

### Pages

| Page | Route | Composants clés |
|------|-------|-----------------|
| Dashboard | `/` | MarketOverview, LivePositions, Signals |
| Backtest | `/backtest` | CompareMatrix, ValidationsTable, AssetDetailPanel |
| Journal | `/journal` | Timeline paper+live, NoteEditor |
| Strategies | `/strategies` | RSI2Visualizer, IBSVisualizer |
| — | `/positions` | OpenPositions, ClosedTrades |

### Points forts
- **Tailwind v4** — utility-first, thème cohérent
- **Recharts** — graphiques equity/drawdown synchronisés
- **Framer Motion** — animations fluides
- **Responsive** — fonctionnel sur desktop/tablet

### Points à améliorer
- **Pas de dark mode** — theme unique (light)
- **Pas de PWA** — pas de service worker pour offline
- **Pas de testing E2E** — 0 tests frontend

---

## 9. Docker & Déploiement

### Images

| Image | Base | Usage | Cron |
|-------|------|-------|------|
| `Dockerfile` | `python:3.12-slim` + uv | Scanner daily | 22h15 CET lun-ven |
| `Dockerfile.api` | `python:3.12-slim` + uv + node | API + Frontend | None |

### Architecture Docker Compose

```yaml
services:
  scanner:   # Docker volume data/, logs/
  api:       # Port 8000, héberge aussi le frontend
```

### Points forts
- **Multi-stage build** — frontend compilé dans API image
- **uv** — ~10× plus rapide que pip
- **HEALTHCHECK** — sur l'API
- **Cron intégré** — scanner automatisé sans service externe

### Points à améliorer
- **Pas de `docker-compose.override.yml`** — prod et dev utilisent le même fichier
- **Pas de monitoring** — pas de Prometheus/Grafana
- **Pas de log aggregation** — logs locales uniquement

---

## 10. Tests

**457 tests collectés** via `pytest`

| Fichier | Tests | Couverture |
|---------|-------|------------|
| `test_simulator.py` | ~15 | Moteur simulation |
| `test_pipeline.py` | ~15 | Pipeline validation |
| `test_types.py` | ~13 | Types framework |
| `test_rsi2_strategy.py` | ~19 | RSI2 plugin |
| `test_ibs_strategy.py` | ~23 | IBS plugin |
| `test_tom_strategy.py` | ~21 | TOM plugin |
| `test_donchian_strategy.py` | ~27 | Donchian plugin |
| `test_db.py` | ~57 | SQLite + paper + live + API |
| `test_api.py` | ~36 | FastAPI endpoints |
| `test_daily_scanner.py` | ~33 | Scanner multi-stratégie |
| `test_monthly_refresh.py` | ~18 | Monthly refresh |
| `test_runner.py` | ~21 | CLI runner |
| `test_indicator_cache.py` | — | Cache indicateurs |
| `test_fee_model.py` | — | Fee models |
| `test_universe_loader.py` | ~8 | Chargement univers YAML |
| `test_report_save.py` | ~4 | Sauvegarde rapport JSON |
| `test_notifier.py` | — | Telegram notifications |

### Points forts
- **Fixtures partagées** (`conftest.py`) — loader, DB, strategy instances
- **Gap-aware** — tests respectent l'anti-look-ahead
- **Couverture plugins** — chaque stratégie a ses tests unitaires

### Points à améliorer
- **0 tests frontend E2E** — pas de Playwright/Cypress
- **0 tests d'intégration API complets** — tests endpoint mais pas de flow complet
- **Pas de mutation testing** — pour vérifier la robustesse des tests

---

## 11. Audit d'exécution (IBS Exit Timing)

**Fichier** : `scripts/compare_ibs_exit_timing.py` (218 lignes)

Post-process les trades IBS pour comparer :
- **Exit close[i]** (backtest standard)
- **Exit open[i+1]** (exécution réelle next-day open)

Permet de quantifier le biais directionnel de l'exit IBS > 0.8.

### Résultats

Le script montre que l'exit open[i+1] est **conservatif** (voire plus profitable) que close[i]. Cela confirme que le backtest n'optimise pas en regardant le high du jour pour sortir.

---

## 12. Contraintes critiques documentées

| Contrainte | Détail | Impact |
|------------|--------|--------|
| **Compte USD obligatoire** | FX 0.25%/trade (compte EUR) tue l'edge | Round-trip ~0.62% vs ~0.12% |
| **Round-trip US stocks** | ~0.12% ($1 commission + 0.05% spread) | Viable pour stratégies court-terme |
| **Round-trip US ETFs** | ~0.07% ($1 commission + 0.03% spread) | Encore plus favorable |
| **Long-only** | Pas de SHORT implémenté | Direction.SHORT dans types.py mais non utilisé |
| **Daily only** | Pas de multi-TF | Intervalle minimum = 1 jour |

---

## 13. Comparaison avec recommandations SCALP_RADAR_AUDIT

Le fichier `docs/SCALP_RADAR_AUDIT.md` (481 lignes) documentait les bonnes pratiques de scalp-radar. Voici ce qui a été suivi ou non :

### ✅ Suivi

| Recommandation | Implémentation signal-radar |
|---------------|----------------------------|
| Moteur unique | `engine/simulator.py` — 1 moteur générique |
| BaseStrategy minimaliste | 5 méthodes abstraites, pas de multi-TF |
| Indicator cache | `build_cache()` pré-calcule tous les indicateurs |
| Config YAML | `config/production_params.yaml` + univers YAML |
| Pipeline standardisé | `validation/pipeline.py` — 10 étapes |
| Test avec stratégies factices | Fixtures dans `conftest.py` |

### ❌ Non suivi / Non applicable

| Recommandation | Raison |
|---------------|--------|
| Auto-registration décorateur | Pas de registry — imports manuels dans CLI |
| Pydantic par stratégie | Config simple via YAML, pas de Pydantic |
| Monte Carlo + DSR dans WFO | Implémentés mais pas dans le pipeline principal (pipeline utilise 48 combos directes) |
| Multi-position / grid | Pas nécessaire — long-only single position |
| Event-driven loop | Vectorisé via `simulate()` — suffisant pour daily |

### 🔄 Partiellement suivi

| Recommandation | Status |
|---------------|--------|
| Grading A+ → F | Pas de grading automatique — verdict VALIDATED/REJECTED/WATCHLIST |
| SQLite async | `data/db.py` utilise `sqlite3` synchrone — OK pour la taille de données |

---

## 14. Résumé — Points forts / Points à améliorer

### Points forts ✅

1. **Architecture simple et cohérente** — 1 moteur, 1 cache, 1 pipeline
2. **Validation rigoureuse** — robustesse 48 combos + t-test + sous-périodes
3. **Anti-look-ahead strict** — signal sur [i-1], action sur open[i]
4. **Gap-aware exits** — gestion correcte des overnight gaps
5. **Fee model réaliste** — $1 commission + spread, pas juste 0.1%
6. **Tests gap-aware** — 457 tests qui respectent la timing rules
7. **Docker + cron** — scanner automatisé sans service externe
8. **Dashboard complet** — signaux, positions, journal, visualisations
9. **Documenté** — PHASE1/2_RESULTS, WORKFLOW_BACKTEST, ROADMAP

### Points à améliorer 🔧

1. **Pas de registry automatique** — ajouter une stratégie = modifier 2+ fichiers
2. **Pas de dark mode frontend** — thème unique
3. **0 tests E2E frontend** — pas de Playwright/Cypress
4. **Pas d'authentification API** — ouvert sur le LAN
5. **Pas de monitoring** — pas de Prometheus/Grafana
6. **Pas de log aggregation** — logs locales uniquement
7. **DB sans backup automatique** — pas de VACUUM/ANALYZE scheduled
8. **Pas de Grading A-F** — verdict binaire (VALIDATED/REJECTED/WATCHLIST)
9. **Monte Carlo / DSR pas dans pipeline principal** — implémentés mais non utilisés par `validate()`
10. **Docker compose unique** — pas de override pour dev vs prod

---

## 15. Tests recommandés pour compléter la couverture

| Test manquant | Priorité | Description |
|---------------|----------|-------------|
| E2E scanner → DB | Haute | Vérifier que daily_scanner.py remplit correctly la DB |
| Paper vs Live compare | Haute | Comparer slippage réel vs backtest sur 30+ trades |
| API auth | Moyenne | Ajouter authentification si exposé sur Internet |
| DB backup | Moyenne | Script de backup SQLite automatique |
| Docker override dev | Basse | `docker-compose.override.yml` pour développement local |

---

## 16. Sécurité FX — Audit FX implicite

### Ce qui est documenté

Le projet documente clairement (CLAUDE.md, PHASE2_RESULTS.md) que :

- **Compte USD obligatoire** sur Saxo/IBKR
- FX conversion 0.25%/trade détruit l'edge short-terme
- Round-trip USD stocks : ~0.12%
- Round-trip EUR : ~0.55% (non viable)

### Ce qui n'est pas自动化

Il n'y a **pas de script d'audit FX automatique**. Le contrôle est :
- **Manuel** : l'utilisateur doit confirmer qu'il utilise un compte USD
- **Documentaire** : la contrainte est dans CLAUDE.md et WORKFLOW_BACKTEST.md

**Pour formaliser** : ajouter un check dans `daily_scanner.py` ou `scripts/monthly_refresh.py` qui log un warning si le fee_model n'est pas `us_stocks_usd_account`.

---

*Document généré Mars 2026 — Phase 6 (Quantitative Forensic & Stability)*
