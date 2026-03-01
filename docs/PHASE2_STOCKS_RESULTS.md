# Phase 2 — Expansion stocks individuels US

Période : 2026-03-01
Objectif : remplacer l'univers ETFs ($100k) par des actions individuelles viables à $10k.

---

## Contexte : pourquoi passer aux stocks ?

L'univers ETFs (SPY/QQQ/IWM/DIA/EFA) est validé à $100k (PF OOS 1.36) mais marginal à $10k
(PF 1.15, AvgPnL $1.56). Les ETFs sont trop liquides pour pullback profond : un RSI(2) < 10
correspond à un drop de ~1.5%, soit un rebond attendu de ~0.5%.

Sur des actions individuelles, les pullbacks RSI(2) < 10 sont de l'ordre de 5-10%,
le rebond attendu est proportionnellement plus large → edge supérieur.

---

## Step 11 — Univers 15 actions US (validate_rsi2_stocks.py)

**Univers testé** : 15 large-caps, différents secteurs (tech, finance, défensif, énergie, retail).
**Période OOS** : 2014-2025. **Capital** : $10 000, whole shares (floor). **Fee model** : `us_stocks_usd_account`.

### Résultats OOS 2014-2025 — triés par PF

| Ticker | Trades | WR | PF | Sharpe | Net% | AvgRet% | AvgPnL$ | Skipped |
|--------|--------|----|----|--------|------|---------|---------|---------|
| META | 84 | 74% | 2.98 | 1.09 | +18.4% | +0.200% | $21.94 | 0 |
| MSFT | 78 | 73% | 1.74 | 0.48 | +6.9% | +0.085% | $8.89 | 0 |
| GOOGL | 78 | 68% | 1.66 | 0.49 | +8.3% | +0.100% | $10.59 | 0 |
| AMZN | 71 | 65% | 1.48 | 0.35 | +5.8% | +0.078% | $8.17 | 0 |
| NVDA | 86 | 67% | 1.48 | 0.34 | +13.6% | +0.142% | $15.84 | 0 |
| GS | 63 | 63% | 1.44 | 0.30 | +3.9% | +0.059% | $6.16 | 0 |
| AMD | 73 | 62% | 1.29 | 0.19 | +8.6% | +0.104% | $11.84 | 0 |
| AAPL | 82 | 66% | 1.20 | 0.18 | +2.9% | +0.034% | $3.55 | 0 |
| WMT | 69 | 71% | 1.13 | 0.09 | +0.9% | +0.012% | $1.29 | 0 |
| CAT | 67 | 63% | 1.06 | 0.05 | +0.9% | +0.011% | $1.27 | 0 |
| KO | 68 | 65% | 1.00 | -0.01 | -0.0% | -0.001% | -$0.04 | 0 |
| XOM | 46 | 54% | 1.00 | -0.01 | -0.0% | -0.003% | -$0.09 | 0 |
| TSLA | 51 | 63% | 0.98 | -0.03 | -0.5% | -0.028% | -$1.00 | 0 |
| JPM | 82 | 60% | 0.91 | -0.09 | -1.3% | -0.018% | -$1.63 | 0 |
| JNJ | 65 | 54% | 0.62 | -0.40 | -3.0% | -0.047% | -$4.59 | 0 |

### Poolé vs ETFs

| Univers | Trades | WR | PF | Sharpe | AvgRet% | AvgPnL$ |
|---------|--------|----|----|--------|---------|---------|
| ETFs (5, $10k) | 380 | 69% | 1.15 | 0.28 | +0.015% | $1.56 |
| **Stocks (15, $10k)** | **1063** | **65%** | **1.30** | **0.69** | **+0.055%** | **$6.15** |

**t-test poolé** : t=2.27, p=0.0116 — significatif.

### Candidats retenues (PF > 1.3) : META, MSFT, GOOGL, AMZN, NVDA, GS

---

## Step 12 — Robustesse 6 candidats (validate_rsi2_stocks_robustness.py)

### V1 — Robustesse paramétrique (48 combos)

Grille : RSI_threshold ∈ {5,10,15,20} × SMA_trend ∈ {150,200,250} × SMA_exit ∈ {3,5,7,10}

| Ticker | Combos PF>1 | %Profitable | Best PF | Worst PF | Median PF | Robuste? |
|--------|-------------|-------------|---------|----------|-----------|----------|
| META | 48/48 | 100% | 5.05 | 1.70 | 2.58 | ✅ OUI |
| MSFT | 48/48 | 100% | 7.60 | 1.45 | 2.16 | ✅ OUI |
| GOOGL | 48/48 | 100% | 2.56 | 1.32 | 1.85 | ✅ OUI |
| NVDA | 48/48 | 100% | 2.70 | 1.47 | 1.94 | ✅ OUI |
| AMZN | 42/48 | 88% | 1.92 | 0.60 | 1.44 | ✅ OUI |
| GS | 23/48 | 48% | 1.74 | 0.55 | 0.97 | ❌ NON |

Seuil : > 80% combos profitables.

### V2 — Stabilité sous-périodes

Split OOS-A 2014-01 → 2019-06 / OOS-B 2019-07 → 2025-01.

| Ticker | OOS-A Trades | PF-A | OOS-B Trades | PF-B | Stable? |
|--------|-------------|------|-------------|------|---------|
| META | 39 | 6.26 | 38 | 3.19 | ✅ OUI |
| MSFT | 39 | 1.81 | 31 | 2.43 | ✅ OUI |
| GOOGL | 37 | 1.07 | 33 | 2.45 | ✅ OUI |
| NVDA | 36 | 1.42 | 43 | 2.10 | ✅ OUI |
| AMZN | 42 | 2.59 | 26 | 0.92 | ❌ NON |
| GS | 28 | 2.36 | 27 | 2.09 | ✅ OUI |

Seuil : PF > 1.0 dans les deux sous-périodes.

### V3 — Significativité statistique (t-test par stock)

| Ticker | Trades | Mean Ret% | t-stat | p-value | Significatif? |
|--------|--------|-----------|--------|---------|---------------|
| META | 84 | +0.200% | 3.58 | 0.0003 | ✅ p < 0.05 |
| MSFT | 78 | +0.085% | 1.60 | 0.057 | ✅ p < 0.10 |
| GOOGL | 78 | +0.100% | 1.62 | 0.055 | ✅ p < 0.10 |
| NVDA | 86 | +0.142% | 1.11 | 0.135 | ❌ p > 0.10 |
| AMZN | 71 | +0.078% | 1.15 | 0.126 | ❌ p > 0.10 |
| GS | 63 | +0.059% | 0.99 | 0.162 | ❌ p > 0.10 |

Seuil : p < 0.10 (peu de trades par stock → puissance faible, assouplissement justifié).

### Matrice de décision finale

| Ticker | Robuste >80% | Stable | Signif p<0.10 | VERDICT |
|--------|-------------|--------|---------------|---------|
| **META** | ✅ 100% | ✅ | ✅ | **VALIDÉ** |
| **MSFT** | ✅ 100% | ✅ | ✅ | **VALIDÉ** |
| **GOOGL** | ✅ 100% | ✅ | ✅ | **VALIDÉ** |
| NVDA | ✅ 100% | ✅ | ❌ | WATCHLIST |
| AMZN | ✅ 88% | ❌ | ❌ | REJETÉ |
| GS | ❌ 48% | ✅ | ❌ | REJETÉ |

---

## Univers de production (v2.0)

| Rôle | Tickers | Fee model |
|------|---------|-----------|
| Actif (signaux BUY auto) | META, MSFT, GOOGL | us_stocks_usd_account |
| Watchlist (indicateurs seulement) | NVDA | us_stocks_usd_account |

**NVDA** : 100% robust, stable — pas encore significatif (p=0.135, ~86 trades OOS).
À promouvoir dans l'univers actif si la p-value passe sous 0.10 avec un historique plus long.

---

## Comparaison fee models

| Fee model | Commission | Spread | FX | Round-trip |
|-----------|-----------|--------|----|-----------|
| us_stocks_usd_account | $1 | 0.05% | 0% | ~0.12% |
| us_etfs_usd_account | $1 | 0.03% | 0% | ~0.07% |
| us_stocks (compte EUR) | $1 | 0.05% | 0.25% | ~0.62% |

---

## Findings critiques

### 1. Stocks > ETFs à $10k grâce aux pullbacks plus profonds

RSI(2) < 10 sur action = drop de 5-10% → rebond attendu proportionnellement plus large.
AvgPnL $6.15 (stocks) vs $1.56 (ETFs) : 4× plus de PnL moyen par trade.

### 2. La robustesse est un meilleur filtre que le PF brut

GS (PF 1.44) rejeté car 48% combos profitables — edge fragile, dépend des params exacts.
AMZN (PF 1.48) rejeté car PF-B = 0.92 en 2019-2025 — edge non persistant.
Un PF élevé sur la période complète peut masquer un collapse en sous-période récente.

### 3. Défensives et énergie ne mean-revertent pas

KO, JNJ, XOM : PF < 1.0 ou ≈ 1.0. Ces titres ont des facteurs fondamentaux dominants
(dividendes, oil cycle) qui dominent le signal RSI à court terme. Le MR court-terme
est une propriété des growth/tech equity.

### 4. TSLA : WR 63% mais PF 0.98

Taux de victoire élevé mais les pertes sur les mauvais trades écrasent les gains.
Volatilité trop extrême — les "pullbacks" RSI(2) < 10 peuvent être de vrais krach.

---

## Timeline Step 11-12

| Step | Script | Résultat |
|------|--------|---------|
| 11 | validate_rsi2_stocks.py | 15 stocks testés, 6 candidats PF > 1.3 |
| 12 | validate_rsi2_stocks_robustness.py | 3 validés, 1 watchlist, 2 rejetés |
| 13 | Mise à jour scanner + production_params.yaml | Univers stocks opérationnel |
