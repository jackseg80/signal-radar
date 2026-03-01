# Phase 1 — Backtesting & Strategy Validation

> **Note:** Phase 1 validated ETFs (SPY, QQQ, IWM, DIA, EFA) at $100k.
> Production scanner now uses individual stocks (META, MSFT, GOOGL) at $10k.
> See [config/production_params.yaml](../config/production_params.yaml) for current configuration.

Période de travail : janvier–mars 2026
Objectif : identifier une stratégie daily sur ETFs/forex viable pour exécution manuelle sur Saxo.

---

## Stratégie validée : RSI(2) Mean Reversion

### Univers et paramètres

| Paramètre | Valeur | Justification |
|-----------|--------|---------------|
| Universe | SPY, QQQ, IWM, DIA, EFA | Equity US + international développé |
| rsi_period | 2 | Connors canonical |
| rsi_entry_threshold | 10.0 | Pullback modéré (vs 5 = trop peu de trades) |
| sma_trend_period | 200 | Filtre trend long-terme standard |
| sma_trend_buffer | 1.01 | Anti-whipsaw (+PF OOS validé Step 7) |
| sma_exit_period | 5 | Exit rapide après rebond |
| sl_percent | 0.0 | Pas de SL (MR = sortie naturelle par SMA5) |
| position_fraction | 0.2 | 20% du capital par trade |
| cooldown_candles | 0 | Pas de cooldown |
| Fee model | us_etfs_usd_account | $1 commission + 0.03% spread, pas de FX |

### Résultats IS / OOS

| Période | Trades | WR | Sharpe | PF | Net |
|---------|--------|----|--------|----|-----|
| Full (2005-2025) | 692 | 69% | 0.83 | 1.47 | +33.6% |
| IS (2005-2014) | 278 | 69% | 1.11 | 1.70 | +19.0% |
| OOS (2014-2025) | 380 | 69% | 0.65 | 1.36 | +14.2% |

### Résultats per-asset (full 2005-2025)

| Asset | Trades | WR | Sharpe | PF | Net |
|-------|--------|----|--------|----|-----|
| SPY | 142 | 72% | 0.30 | 1.37 | +5.5% |
| QQQ | 152 | 68% | 0.63 | 1.83 | +12.0% |
| IWM | 129 | 66% | 0.30 | 1.37 | +6.2% |
| DIA | 155 | 70% | 0.42 | 1.49 | +6.6% |
| EFA | 114 | 67% | 0.23 | 1.29 | +3.4% |

### Tests statistiques OOS

- **t-test (mean return > 0)** : t=2.14, p=0.0166 — significatif au seuil 5%
- **Monte Carlo block bootstrap** : p=0.503 — non applicable (voir note)
- **Robustesse paramétrique** : 48/48 combos PF > 1.0 (100%), 42/48 PF > 1.2 (88%)

> Note Monte Carlo : le block bootstrap teste si l'ordre temporel des trades importe.
> Pour une stratégie MR où chaque trade est quasi-indépendant, le shuffle ne change rien
> → p~0.5 est attendu et normal. Le t-test est le bon outil statistique ici.

---

## Stratégies rejetées

### 1. Donchian Trend Following — US Stocks (10 assets, Steps 1–4)

**Paramètres testés** : Donchian 50/20, trailing 3.0× ATR, SL 10%, long-only, ADX filter.
**WFO** : grille 12 combos (adx_threshold=[0,20], trailing=[3,4,5], sl=[8,10]).

| Metric | Valeur |
|--------|--------|
| IS Return (10 ans) | +4.22% (+0.41% CAGR) |
| OOS Return (5 ans) | -1.08% (-0.22% CAGR) |
| OOS MaxDD | 6.4% |
| WFO grade B+ | 0/10 assets |

**Cause** : les actions large-cap US mean-revertent sur daily — le trend following ne s'applique pas.
NVDA masquait les pertes des 9 autres assets en OOS (AI boom 2023-24).
`position_fraction=0.2` → 80% du capital en cash → rendement tué.

---

### 2. Donchian Trend Following — Forex (7 majors, Step 8)

**Paramètres** : Donchian 50/20, ADX > 25, trailing 3.0× ATR, SL 10%, long+short.
**Univers** : EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD.

| Période | Trades | WR | PF |
|---------|--------|----|----|
| IS (2003-2015) | 200 | 41% | 0.95 |
| OOS (2015-2025) | 149 | 34% | 0.50 |

**Cause** : le forex majors est en régime range-bound post-2015. Faible volatilité
directionnelle. Seul USDCAD est rentable (PF 1.43). Les 6 autres perdent.

---

### 3. RSI(2) sur ETFs non-equity (Step 9)

**Période** : 2005-2025, mêmes params que la stratégie validée.

| Asset | Classe | Trades OOS | PF OOS | Décision |
|-------|--------|-----------|--------|----------|
| GLD | Or/Commodity | 59 | 0.95 | Rejeté — l'or trend, ne MR pas |
| TLT | Obligations 20y+ | 52 | 1.04 | Rejeté — edge MR faible |
| XLE | Énergie | 64 | 1.02 | Rejeté — trop cyclique |
| EFA | International développé | 73 | 1.18 | **Inclus** (PF > 1.1) |

---

## Findings critiques

### 1. Compte USD obligatoire sur Saxo

Le FX de conversion (0.25%/trade pour un compte EUR) détruit l'edge :

| Fee model | Round-trip | WR SPY | PF SPY |
|-----------|-----------|--------|--------|
| Saxo EUR (FX 0.25%) | ~0.55% | 53% | 0.65 |
| Compte USD (pas de FX) | ~0.07% | 71% | 1.47 |

La stratégie n'est viable **que** sur un sous-compte USD Saxo.

### 2. Mean reversion = phénomène equity

RSI(2) fonctionne sur SPY/QQQ/IWM/DIA/EFA mais pas sur GLD, TLT, XLE.
L'or trend, les obligations ont des cycles longs, l'énergie est trop cyclique.
Le MR court-terme est une propriété des marchés equity liquides et diversifiés.

### 3. Trend following daily sur forex mort post-2015

PF OOS 0.50 sur 7 paires majors. La faible volatilité directionnelle post-2015
(Bank of Japan, BCE, faible inflation) a tué l'edge Turtle Traders sur le daily.

### 4. Bug double-counting entry_fee (corrigé)

`capital += capital_allocated - entry_fee + pnl` soustrayait `entry_fee` deux fois
car `_close_trend_position()` l'inclut déjà dans le PnL. Corrigé en
`capital += capital_allocated + pnl`. Impact : léger sur les métriques finales
(les returns par trade étaient légèrement sous-estimés).

### 5. Monte Carlo block bootstrap non applicable au MR

Le block bootstrap teste si l'ordre temporel des trades importe. Pour MR (trades
indépendants), il donne systématiquement p~0.5 — sans signification. Utiliser
le t-test sur mean(return_par_trade) > 0 (p=0.0166 ici).

---

## Timeline des étapes

| Step | Description | Résultat |
|------|-------------|---------|
| 1-4 | Engine gap-aware, WFO, Donchian US stocks | REJECTED |
| 5 | RSI(2) sur SPY — benchmark Connors | Validé sans FX |
| 6 | Portfolio 4 ETFs (SPY/QQQ/IWM/DIA) | PF OOS 1.35 |
| 7 | Robustesse : MC + sensibilité 48 combos | 100% rentable |
| 8 | Donchian forex 7 paires | REJECTED PF 0.50 |
| 9 | Univers élargi GLD/TLT/XLE/EFA | EFA seul OK |
| 10 | Portfolio final 5 ETFs + t-test | **PF 1.36, p=0.0166** |
| 11 | Documentation + production params | Phase 2 ready |

---

## Architecture des fichiers

```
engine/
  indicators.py              — SMA, EMA, Donchian, ATR, ADX, RSI (Wilder)
  indicator_cache.py         — Build cache indicateurs par asset
  fee_model.py               — FeeModel + presets (US_ETFS_USD, FOREX, EU_STOCKS...)
  backtest_config.py         — BacktestConfig (symbol, capital, slippage, fee_model)
  fast_backtest.py           — Trend following (Donchian/EMA, trailing ATR stop)
  mean_reversion_backtest.py — RSI(2) mean reversion (SMA filter + SMA exit)

data/
  base_loader.py             — BaseDataLoader + to_cache_arrays()
  yahoo_loader.py            — YahooLoader, cache parquet, adj-close O/H/L

optimization/
  walk_forward.py            — WFO en barres (trading days, pas calendrier)
  overfit_detection.py       — Monte Carlo block bootstrap, DSR, stabilité

tests/
  test_mean_reversion.py     — 12 tests RSI(2)
  test_fee_model.py          — Tests fee model
  test_indicator_cache.py    — Tests cache indicateurs
  test_fast_backtest.py      — Tests trend following
  conftest.py                — Fixtures partagées

scripts/
  validate_rsi2_final.py     — Step 10 : portfolio final [REFERENCE PRODUCTION]
  validate_rsi2_spy.py       — Step 5  : SPY seul, comparaison fees
  validate_rsi2_portfolio.py — Step 6  : 4 ETFs equity
  validate_rsi2_robustness.py— Step 7  : Monte Carlo + sensibilité
  validate_rsi2_expanded.py  — Step 9  : GLD/TLT/XLE/EFA
  validate_donchian_forex.py — Step 8  : REJECTED

config/
  production_params.yaml     — Params figés pour Phase 2
  fee_models.yaml            — Modèles de frais
  assets_etf_us.yaml         — Univers ETFs equity US

docs/
  PHASE1_RESULTS.md          — Ce fichier
```
