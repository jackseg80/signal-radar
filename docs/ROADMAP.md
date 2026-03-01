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
À $10k de capital, les frais fixes ($1/trade) pèsent 3.4× plus en proportion. Les ETFs (volatilité faible, pullbacks de ~1.5%) ne génèrent pas assez de return par trade pour couvrir les frais. Les actions individuelles (pullbacks de 5-10%) résolvent le problème :

| | ETFs ($10k) | Stocks ($10k) |
|---|---|---|
| PF OOS | 1.15 | 1.30 |
| Avg PnL/trade | $1.56 | $6.15 |
| Sharpe | 0.28 | 0.69 |

### Stocks validés (production)

| Ticker | PF   | WR  | Robustesse 48 combos | Sous-périodes  | t-test   | Verdict        |
|--------|------|-----|----------------------|----------------|----------|----------------|
| META   | 2.98 | 74% | 100%                 | 6.26 / 3.19    | p=0.0003 | ✅ VALIDÉ      |
| MSFT   | 1.74 | 73% | 100%                 | 1.81 / 2.43    | p=0.057  | ✅ VALIDÉ      |
| GOOGL  | 1.66 | 68% | 100%                 | 1.07 / 2.45    | p=0.055  | ✅ VALIDÉ      |
| NVDA   | 1.48 | 67% | 100%                 | 1.42 / 2.10    | p=0.135  | 👀 WATCHLIST   |
| AMZN   | 1.48 | 65% | 88%                  | 2.59 / 0.92    | p=0.126  | ❌ Instable    |
| GS     | 1.44 | 63% | 48%                  | 2.36 / 2.09    | p=0.162  | ❌ Fragile     |

### Livrables
- Scanner quotidien avec state machine (null → pending → open → null)
- Watchlist mode (NVDA — track sans trader)
- Notifications Telegram (signal + rapport hebdo)
- Docker + cron (22h15 CET, dim-ven)
- 80 tests passing
- Documentation complète (CLAUDE.md, README.md, PHASE1_RESULTS.md, PHASE2_RESULTS.md)

---

## Phase 2.5 — Live Validation 🔄 EN COURS

**Période :** Mars - Juin 2026
**Objectif :** Valider la stratégie en conditions réelles avant de scale up.

### Pré-requis broker

| Action | Statut | Détails |
|--------|--------|---------|
| Sous-compte USD Saxo | ❌ À ouvrir | Contacter support Saxo Switzerland |
| Test achat META (actions, pas CFD) | ❌ À vérifier | Passer un ordre de 1 part |
| Capital $10k transféré | ❌ À faire | Virement vers sous-compte USD |

### Dry run (2-3 semaines)

- Observer les signaux quotidiens sans trader
- Vérifier la cohérence signaux vs charts
- S'assurer que le scanner tourne sans problème
- Prendre le rythme opérationnel (signal le soir → exécution le matin)

### Live trading (~3-4 mois, objectif 20-30 trades)

- Premier cycle complet : BUY → HOLD → SELL
- Tracking dans signal_history.csv
- Mesurer le slippage réel (exit close backtest → exit next open live)
- Comparer PF/WR live vs backtest

### Go/no-go à 30 trades

| Métrique | Continuer | Investiguer | Arrêter |
|----------|-----------|------------|---------|
| PF live  | > 1.15    | 1.0 — 1.15 | < 1.0   |
| WR live  | > 60%     | 55-60%     | < 55%   |
| Slippage | < 0.1%    | 0.1-0.2%   | > 0.2%  |

### Décision NVDA (~6 mois)

Suivi paper trading via watchlist. Si après ~50 would-trigger trades la significativité s'améliore (p < 0.10), passer en actif. Sinon, retirer de la watchlist.

---

## Phase 3 — Dashboard Web 📋 PLANIFIÉ

**Période estimée :** Q2-Q3 2026
**Objectif :** Remplacer CSV + Telegram par un dashboard web interactif.

### Architecture envisagée

| Composant | Technologie |
|-----------|------------|
| Backend | FastAPI |
| Base de données | SQLite (→ PostgreSQL si scale) |
| Frontend | React ou HTML/JS simple |
| Hébergement | Docker sur 192.168.1.200 (même serveur) |

### Features

| Feature | Priorité | Description |
|---------|----------|-------------|
| Tableau d'assets | P0 | Tous les assets avec RSI, SMA, trend, distance au signal, trié par proximité |
| Journal de trades | P0 | Entry, exit, PnL réel, PnL backtest attendu, écart |
| Equity curve live | P1 | Graphe cumulé trades réels vs backtest |
| Signal history | P1 | Historique complet des signaux avec filtres |
| Alertes proximité | P2 | "NVDA s'approche du signal" (RSI=15, en baisse depuis 3 jours) |
| Multi-utilisateur | P3 | Authentification (si partage avec d'autres traders) |

### DB Schema (ébauche)

- `assets` : symbol, market, strategy, status (active/watchlist/rejected)
- `daily_indicators` : date, symbol, close, rsi2, sma200, sma5, trend_ok
- `signals` : date, symbol, signal_type, details, notified
- `trades` : symbol, entry_date, entry_price, exit_date, exit_price, pnl_real, pnl_backtest
- `config` : params, fee_model, capital

---

## Phase 4 — Scale Up 📋 PLANIFIÉ

**Période estimée :** Q3-Q4 2026
**Pré-requis :** PF live > 1.15 sur 30+ trades réels.

### Augmentation de capital

| Capital       | Actions possibles                             | PF attendu |
|---------------|-----------------------------------------------|------------|
| $10k (actuel) | META, MSFT, GOOGL                             | 1.30       |
| $20k          | + meilleur sizing                             | ~1.25      |
| $50k+         | + réintégrer ETFs (SPY, QQQ, IWM, DIA, EFA)  | ~1.33      |
| $100k         | Conditions du backtest original               | 1.36       |

### Élargissement univers

| Action | Pré-requis | Pipeline |
|--------|-----------|----------|
| NVDA → actif | p-value < 0.10 | Watchlist → validate → promote |
| Nouvelles actions US | Screening | Backtest → robustesse 48 combos → sous-périodes → t-test |
| ETFs réintégrés | Capital $50k+ | Même params, frais fixes dilués |
| Marchés européens | Nouvelle recherche | Fee model EU, identifier les candidats MR |

---

## Phase 5 — Automatisation Complète 📋 VISION LONG TERME

**Période estimée :** 2027+
**Pré-requis :** Dashboard opérationnel, historique live positif, capital suffisant.

### Exécution automatique

| Feature | Description | Complexité |
|---------|------------|-----------|
| API Saxo | Passage d'ordres automatique | Moyenne — Saxo a une API REST |
| Position sizing dynamique | Kelly criterion ou volatility targeting | Faible — calcul pur |
| Confirmation manuelle | Signal auto → notification → 1 tap pour confirmer | Moyenne |
| Full auto | Signal → ordre → tracking → exit, sans intervention | Élevée |

### Multi-stratégie

| Stratégie | Marché | Status |
|-----------|--------|--------|
| RSI(2) mean reversion | US stocks + ETFs | ✅ Validée |
| Trend following (Donchian/EMA) | Commodities ? Crypto ? | ❌ Rejeté sur forex daily, à explorer sur d'autres marchés |
| Pairs trading / stat arb | US stocks | 💡 Idée — pas encore explorée |
| Momentum mensuel | ETFs sectoriels | 💡 Idée — rotation sectorielle |

---

## Historique des décisions clés

| Date       | Décision | Raison |
|------------|----------|--------|
| Fév 2026   | Créer signal-radar séparé de scalp-radar | Pas de coupling avec le système crypto live |
| Fév 2026   | Rejeter Donchian TF sur stocks | WFO grade F — stocks mean-revertent |
| Mars 2026  | Adopter RSI(2) Connors (params fixes) | Publié 2004, edge comportemental persistant, pas d'optimisation |
| Mars 2026  | Rejeter Donchian TF sur forex | PF 0.50 OOS — range-bound post-2015 |
| Mars 2026  | Imposer compte USD Saxo | FX 0.25%/trade détruit l'edge MR court-terme |
| Mars 2026  | Pivoter ETFs → stocks individuelles ($10k) | Frais fixes $1 trop lourds sur ETFs à petit capital |
| Mars 2026  | Valider META/MSFT/GOOGL, watchlist NVDA | Robustesse 100%, sous-périodes stables, t-test significatif |
| Mars 2026  | Rejeter AMZN (instable) et GS (fragile) | PF 0.92 en 2019-2025 / 48% combos profitables |
