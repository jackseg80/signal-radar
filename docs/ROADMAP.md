# Signal-Radar — Roadmap

## Phase 1 — Backtesting Engine & Strategy Validation ✅ COMPLETE

**Période :** Février-Mars 2026
**Objectif :** Construire un moteur de backtest et trouver une stratégie profitable sur les marchés traditionnels.

### Steps réalisés

| Step | Description | Résultat |
|------|------------|---------|
| 1-4 | Donchian trend following sur 10 US stocks | ❌ REJETÉ — WFO tout grade F (stocks mean-revertent) |
| 5 | RSI(2) Connors sur SPY seul | ✅ Résultats cohérents avec la littérature Connors |
| 6 | RSI(2) portfolio 4 ETFs (SPY, QQQ, IWM, DIA) | ✅ PF 1.35 OOS, 332 trades |
| 7 | Monte Carlo + sensibilité 48 combinaisons params | ✅ 100% des combos profitables OOS |
| 8 | Donchian trend following sur 7 forex majors | ❌ REJETÉ — PF OOS 0.50 (range-bound post-2015) |
| 9 | RSI(2) univers élargi (GLD, TLT, XLE, EFA) | ✅ EFA ajouté, GLD/TLT/XLE rejetés |
| 10 | Validation finale 5 ETFs | ✅ 380 trades, WR 69%, PF 1.36, Sharpe 0.65, p=0.016 |

### Key findings
- Mean reversion = phénomène equity. Pas applicable sur gold, bonds, énergie.
- Trend following mort sur forex daily post-2015.
- RSI(2) Connors (publié 2004) encore profitable 20 ans après — edge comportemental, pas technique.
- 100% robustesse paramétrique = edge structurel, pas fragile.
- Compte USD Saxo obligatoire — FX 0.25%/trade détruit l'edge.

### Livrables
- Moteur backtest mean reversion (gap-aware, anti-look-ahead)
- Moteur backtest trend following (Donchian/EMA)
- Walk-forward optimizer
- Monte Carlo block bootstrap + overfit detection
- 55 tests passing
- `config/production_params.yaml` — params figés

---

## Phase 2 — Daily Signal Scanner & Deployment ✅ COMPLETE

**Période :** 1er Mars 2026
**Objectif :** Scanner quotidien opérationnel déployé en production avec notifications.

### Steps réalisés

| Step | Description | Résultat |
|------|------------|---------|
| 11 | Scanner MVP (5 ETFs) | ✅ daily_scanner.py, positions.json, signal_history.csv, 10 tests |
| 12 | Validation sizing $10k | ✅ ETFs PF 1.15 à $10k — edge trop faible (frais fixes) |
| 12b | RSI(2) sur 15 actions individuelles | ✅ PF 1.30 poolé, 6 candidats PF > 1.3 |
| 13 | Robustesse stocks (48 combos, sous-périodes, t-test) | ✅ 3 validés : META (2.98), MSFT (1.74), GOOGL (1.66) |
| 13b | Scanner v2.0 — univers stocks + watchlist NVDA | ✅ Opérationnel |
| 14 | Docker + Telegram + cron | ✅ Déployé sur serveur Ubuntu (192.168.1.200) |

### Pivot ETFs → Stocks
À $10k de capital, les frais fixes ($1/trade) pèsent 3.4× plus en proportion. Les ETFs (volatilité faible, pullbacks de ~1.5%) ne génèrent pas assez de return par trade pour couvrir les frais. Les actions individuelles (pullbacks de 5-10%) résolvent le problème.

### Stocks validés (production)

| Ticker | PF | WR | Robustesse 48 combos | Sous-périodes | t-test | Verdict |
|--------|-----|-----|---------------------|---------------|--------|---------|
| META | 2.98 | 74% | 100% | 6.26 / 3.19 | p=0.0003 | ✅ VALIDÉ |
| MSFT | 1.74 | 73% | 100% | 1.81 / 2.43 | p=0.057 | ✅ VALIDÉ |
| GOOGL | 1.66 | 68% | 100% | 1.07 / 2.45 | p=0.055 | ✅ VALIDÉ |
| NVDA | 1.48 | 67% | 100% | 1.42 / 2.10 | p=0.135 | 👀 WATCHLIST |
| AMZN | 1.48 | 65% | 88% | 2.59 / 0.92 | p=0.126 | ❌ Instable |
| GS | 1.44 | 63% | 48% | 2.36 / 2.09 | p=0.162 | ❌ Fragile |

### Livrables
- Scanner quotidien avec state machine (null → pending → open → null)
- Watchlist mode (NVDA — track sans trader)
- Notifications Telegram (signal + rapport hebdo)
- Docker + cron (22h15 CET, dim-ven)
- 80 tests passing
- Documentation complète

---

## Phase 3 — Backtesting Framework ✅ COMPLETE

**Période :** Mars 2026
**Objectif atteint :** Framework modulaire opérationnel.

### Steps Phase 3

| Step | Description | Résultat |
| ---- | ----------- | -------- |
| 15 | Audit scalp-radar | ✅ docs/SCALP_RADAR_AUDIT.md |
| 16 | Design framework | ✅ BaseStrategy, moteur unique, pipeline |
| 17 | Types + BaseStrategy + Moteur | ✅ 36 tests |
| 18 | Migration RSI(2) MR | ✅ 19 tests |
| 19 | Migration Donchian TF | ✅ 27 tests |
| 20 | Pipeline de validation | ✅ CLI + 15 tests |
| 21 | Vérification migration | ✅ 534 trades, $0.00 diff sur 4 stocks |
| 22 | Documentation + nettoyage | ✅ |

### Critères de succès — tous atteints

- ✅ Ajouter une nouvelle stratégie = 1 fichier + hériter BaseStrategy
- ✅ Valider/rejeter une stratégie = `python -m cli.validate <preset>`
- ✅ Résultats RSI(2) identiques à Phase 2 (vérification trade par trade)
- ✅ 177 tests passing

### Résultats pipeline (nouveau framework)

| Ticker | Trades | WR | PF | Robust | Stable | Signif | Verdict |
| ------ | ------ | -- | -- | ------ | ------ | ------ | ------- |
| META | 93 | 74% | 3.49 | 100% | ✅ | ✅ | VALIDATED |
| MSFT | 85 | 72% | 1.66 | 100% | ✅ | ✅ | VALIDATED |
| GOOGL | 90 | 67% | 1.72 | 100% | ✅ | ✅ | VALIDATED |
| NVDA | 96 | 67% | 1.48 | 100% | ✅ | ✅ | VALIDATED |
| AMZN | 74 | 65% | 1.39 | 88% | ❌ | ❌ | REJECTED |
| GS | 70 | 64% | 1.55 | 50% | ✅ | ✅ | REJECTED |

T-test poolé : 508 trades, t=4.27, p=0.0000.

Note : les PnL par trade sont identiques à Phase 2 (vérifié par `scripts/verify_migration.py`).
La différence de nombre de trades vient du warmup amélioré dans le nouveau pipeline.
NVDA passe de WATCHLIST à VALIDATED (plus de trades → significativité atteinte).

### Livrables Phase 3

- `strategies/base.py` — BaseStrategy ABC
- `strategies/rsi2_mean_reversion.py` — RSI(2) Connors plugin
- `strategies/donchian_trend.py` — Donchian TF plugin
- `engine/simulator.py` — Moteur unique générique (start_idx/end_idx)
- `engine/types.py` — Direction, ExitSignal, Position, TradeResult, BacktestResult
- `validation/pipeline.py` — Pipeline complet : robustesse + sous-périodes + t-test + verdict
- `cli/validate.py` — CLI : `python -m cli.validate <preset>`
- `scripts/verify_migration.py` — Preuve migration (534 trades, $0.00 diff)
- Anciens moteurs marqués DEPRECATED (conservés pour référence)
- 177 tests passing

---

## Phase 4 — Live Validation 📋 PLANIFIÉ

**Période :** Avril - Juillet 2026
**Objectif :** Valider la stratégie en conditions réelles.
**Pré-requis :** Phase 3 complète + sous-compte USD Saxo + capital $10k.

### Pré-requis broker

| Action | Statut |
|--------|--------|
| Sous-compte USD Saxo | ❌ À ouvrir |
| Test achat META (actions, pas CFD) | ❌ À vérifier |
| Capital $10k transféré | ❌ À faire |

### Plan

- Dry run 2-3 semaines (observer sans trader)
- 20-30 trades réels (~3-4 mois)
- Go/no-go : PF live > 1.15 → continuer, < 1.0 → investiguer
- Décision NVDA après ~6 mois

---

## Phase 5 — Dashboard Web 📋 PLANIFIÉ

**Période estimée :** Q3-Q4 2026
**Objectif :** Dashboard web interactif remplaçant CSV + Telegram.

### Features

| Feature | Priorité |
|---------|----------|
| Tableau d'assets (RSI, SMA, distance au signal, trend) | P0 |
| Journal de trades (PnL réel vs backtest) | P0 |
| Equity curve live | P1 |
| Alertes proximité ("NVDA s'approche du signal") | P2 |
| Comparaison multi-stratégie | P2 |

---

## Phase 6 — Scale Up 📋 PLANIFIÉ

**Période estimée :** 2027
**Pré-requis :** PF live > 1.15 sur 30+ trades.

- Augmenter capital ($20k → $50k → $100k)
- Réintégrer ETFs quand capital le permet
- Ajouter des stocks validés (pipeline Phase 3)
- Explorer marchés européens

---

## Phase 7 — Automatisation Complète 📋 VISION LONG TERME

- API Saxo (exécution automatique)
- Position sizing dynamique (Kelly / vol targeting)
- Multi-stratégie simultané
- Full auto (signal → ordre → tracking → exit)

---

## Historique des décisions clés

| Date | Décision | Raison |
|------|----------|--------|
| Fév 2026 | Créer signal-radar séparé de scalp-radar | Pas de coupling avec le système crypto live |
| Fév 2026 | Rejeter Donchian TF sur stocks | WFO grade F — stocks mean-revertent |
| Mars 2026 | Adopter RSI(2) Connors (params fixes) | Publié 2004, edge comportemental persistant |
| Mars 2026 | Rejeter Donchian TF sur forex | PF 0.50 OOS — range-bound post-2015 |
| Mars 2026 | Imposer compte USD Saxo | FX 0.25%/trade détruit l'edge MR court-terme |
| Mars 2026 | Pivoter ETFs → stocks individuelles ($10k) | Frais fixes trop lourds sur ETFs à petit capital |
| Mars 2026 | Valider META/MSFT/GOOGL, watchlist NVDA | Robustesse 100%, sous-périodes stables, t-test significatif |
| Mars 2026 | Rejeter AMZN et GS | Instable / fragile aux params |
| Mars 2026 | Prioriser framework backtest (Phase 3) avant live | Besoin d'un système modulaire pour tester de nouvelles stratégies |
| Mars 2026 | Framework backtest Phase 3 complété | 177 tests, migration vérifiée, pipeline opérationnel |
| Mars 2026 | NVDA passe VALIDATED dans le nouveau pipeline | Meilleur warmup → plus de trades → significativité atteinte |
