# Signal Radar — Validation Results

> **Dernière mise à jour :** 2026-03-02
> **OOS Period :** 2014-01-01 → 2025-01-01 (11 ans)
> **Pipeline :** OOS backtest + robustesse paramétrique (48 combos) + stabilité sous-périodes + t-test (one-tailed)
> **Strategies :** RSI(2) Mean Reversion, IBS Mean Reversion, Turn of Month
> **Univers :** 46 US stocks (large cap), 10 broad ETFs, 11 sector ETFs, 7 forex majors
> **Capital :** $10,000 (stocks, whole shares) / $100,000 (ETFs, fractional) / $100,000 (forex, fractional)
> **Frais :** US stocks 0.05% spread + $1 commission, ETFs 0.03% spread + $1, Forex 0.015% spread

---

## 1. Vue d'ensemble

| Univers | Stratégie | V | C | R | Trades | t-stat | p-value |
|---|---|---:|---:|---:|---:|---:|---|
| us_stocks_large | RSI2 | 10 | 5 | 31 | 3 390 | 2.90 | 0.0019 |
| us_stocks_large | IBS | 13 | 3 | 30 | 10 905 | 3.03 | 0.0012 |
| us_stocks_large | TOM | 21 | 6 | 19 | 5 901 | 7.74 | <0.0001 |
| us_etfs_broad | RSI2 | 3 | 3 | 4 | 843 | 3.02 | 0.0013 |
| us_etfs_broad | IBS | 3 | 4 | 3 | 2 553 | 2.82 | 0.0024 |
| us_etfs_broad | TOM | 6 | 2 | 2 | 1 320 | 3.91 | <0.0001 |
| us_etfs_sector | RSI2 | 1 | 4 | 6 | 823 | 1.73 | 0.0416 |
| us_etfs_sector | IBS | 1 | 1 | 9 | 2 641 | 2.32 | 0.0101 |
| us_etfs_sector | TOM | 8 | 3 | 0 | 1 374 | 4.64 | <0.0001 |
| forex_majors | IBS | 7 | 0 | 0 | 1 581 | 12.61 | <0.0001 |

**V** = VALIDATED (robust + stable + significant), **C** = CONDITIONAL, **R** = REJECTED

**Observation principale :** TOM a le signal poolé le plus fort (t=7.74, p<10⁻¹⁴ sur les stocks). IBS génère le plus de trades et la meilleure couverture. RSI2 est le plus sélectif. Les trois stratégies sont statistiquement significatives sur tous les univers sauf RSI2 sector (t=1.73, p=0.04 — marginalement significatif).

---

## 2. Tier 1 — Triple Validated

Assets avec VALIDATED ou CONDITIONAL sur les **3 stratégies**. Priorité maximale.

| Asset | RSI2 | PF | Trades | IBS | PF | Trades | TOM | PF | Trades |
|---|:---:|---:|---:|:---:|---:|---:|:---:|---:|---:|
| **META** | V | 3.49 | 93 | V | 1.68 | 302 | V | 1.89 | 132 |
| **V** | V | 2.48 | 86 | V | 1.46 | 315 | V | 1.44 | 132 |
| **NVDA** | V | 1.48 | 96 | V | 2.07 | 314 | V | 1.29 | 132 |
| **MA** | V | 1.86 | 91 | V | 1.41 | 288 | V | 1.37 | 132 |
| **AVGO** | V | 1.59 | 98 | V | 1.43 | 304 | V | 1.45 | 132 |
| **MSFT** | V | 1.66 | 85 | V | 1.54 | 309 | C | 1.23 | 132 |
| **AAPL** | C | 1.33 | 94 | V | 1.51 | 289 | V | 1.40 | 132 |
| **ADBE** | C | 1.45 | 76 | V | 1.31 | 274 | V | 1.31 | 132 |
| **UNH** | C | 1.33 | 95 | C | 1.21 | 279 | V | 1.28 | 132 |

**Détails Tier 1 :**

| Asset | Strat | Trades | WR | PF | Sharpe | Robust | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| META | RSI2 | 93 | 74% | 3.49 | 6.86 | 100% | VALIDATED |
| META | IBS | 302 | 72% | 1.68 | 2.71 | 100% | VALIDATED |
| META | TOM | 132 | 64% | 1.89 | 3.19 | 100% | VALIDATED |
| V | RSI2 | 86 | 77% | 2.48 | 5.36 | 96% | VALIDATED |
| V | IBS | 315 | 69% | 1.46 | 2.26 | 100% | VALIDATED |
| V | TOM | 132 | 58% | 1.44 | 2.29 | 92% | VALIDATED |
| NVDA | RSI2 | 96 | 67% | 1.48 | 2.14 | 100% | VALIDATED |
| NVDA | IBS | 314 | 72% | 2.07 | 3.96 | 100% | VALIDATED |
| NVDA | TOM | 132 | 58% | 1.29 | 2.22 | 100% | VALIDATED |
| MA | RSI2 | 91 | 74% | 1.86 | 3.22 | 100% | VALIDATED |
| MA | IBS | 288 | 67% | 1.41 | 1.82 | 100% | VALIDATED |
| MA | TOM | 132 | 57% | 1.37 | 2.38 | 100% | VALIDATED |
| AVGO | RSI2 | 98 | 69% | 1.59 | 2.72 | 96% | VALIDATED |
| AVGO | IBS | 304 | 62% | 1.43 | 2.18 | 100% | VALIDATED |
| AVGO | TOM | 132 | 61% | 1.45 | 2.99 | 100% | VALIDATED |
| MSFT | RSI2 | 85 | 72% | 1.66 | 2.78 | 100% | VALIDATED |
| MSFT | IBS | 309 | 70% | 1.54 | 2.46 | 100% | VALIDATED |
| MSFT | TOM | 132 | 53% | 1.23 | 1.57 | 100% | CONDITIONAL |
| AAPL | RSI2 | 94 | 69% | 1.33 | 1.75 | 92% | CONDITIONAL |
| AAPL | IBS | 289 | 69% | 1.51 | 2.50 | 100% | VALIDATED |
| AAPL | TOM | 132 | 59% | 1.40 | 2.55 | 100% | VALIDATED |
| ADBE | RSI2 | 76 | 70% | 1.45 | 2.19 | 96% | CONDITIONAL |
| ADBE | IBS | 274 | 68% | 1.31 | 1.62 | 100% | VALIDATED |
| ADBE | TOM | 132 | 61% | 1.31 | 2.06 | 100% | VALIDATED |
| UNH | RSI2 | 95 | 68% | 1.33 | 1.67 | 96% | CONDITIONAL |
| UNH | IBS | 279 | 64% | 1.21 | 1.06 | 94% | CONDITIONAL |
| UNH | TOM | 132 | 58% | 1.28 | 1.83 | 92% | VALIDATED |

---

## 3. Tier 2 — Double Validated

Assets avec VALIDATED ou CONDITIONAL sur exactement **2 stratégies**.

| Asset | RSI2 | PF | IBS | PF | TOM | PF | Note |
|---|:---:|---:|:---:|---:|:---:|---:|---|
| **GE** | V | 1.99 | V | 1.38 | R | 1.07 | TOM inefficace (WR 47%) |
| **GOOGL** | V | 1.72 | V | 1.29 | R | 1.25 | TOM marginal (non-signif) |
| **AMZN** | R | 1.39 | V | 1.46 | V | 1.29 | RSI2 instable (robust 88%) |
| **ORCL** | V | 1.58 | R | 1.01 | V | 1.52 | IBS sans edge (PF~1.0) |
| **AMD** | R | 1.29 | V | 1.32 | V | 1.23 | RSI2 instable (rob 94%, non-stable) |
| **NFLX** | R | 0.87 | C | 1.17 | V | 1.79 | RSI2/IBS faibles, TOM fort |
| **MRK** | C | 1.39 | R | 0.92 | V | 1.27 | IBS sans edge sur pharma |
| **LLY** | R | 0.92 | C | 1.10 | V | 1.51 | Seul TOM exploitable |
| **PG** | C | 1.31 | R | 0.79 | C | 1.09 | Deux CONDITIONAL faibles |

**Détails Tier 2 :**

| Asset | Strat | Trades | WR | PF | Sharpe | Verdict |
|---|---|---:|---:|---:|---:|---|
| GE | RSI2 | 63 | 68% | 1.99 | 3.70 | VALIDATED |
| GE | IBS | 185 | 68% | 1.38 | 1.79 | VALIDATED |
| GE | TOM | 132 | 47% | 1.07 | 0.78 | REJECTED |
| GOOGL | RSI2 | 90 | 67% | 1.72 | 3.19 | VALIDATED |
| GOOGL | IBS | 277 | 66% | 1.29 | 1.42 | VALIDATED |
| GOOGL | TOM | 132 | 56% | 1.25 | 1.57 | REJECTED |
| AMZN | RSI2 | 74 | 65% | 1.39 | 1.87 | REJECTED |
| AMZN | IBS | 267 | 63% | 1.46 | 2.12 | VALIDATED |
| AMZN | TOM | 132 | 58% | 1.29 | 1.95 | VALIDATED |
| ORCL | RSI2 | 82 | 65% | 1.58 | 2.78 | VALIDATED |
| ORCL | IBS | 254 | 62% | 1.01 | 0.10 | REJECTED |
| ORCL | TOM | 132 | 55% | 1.52 | 2.82 | VALIDATED |
| AMD | RSI2 | 80 | 62% | 1.29 | 1.47 | REJECTED |
| AMD | IBS | 247 | 62% | 1.32 | 1.68 | VALIDATED |
| AMD | TOM | 132 | 51% | 1.23 | 1.94 | VALIDATED |
| NFLX | RSI2 | 89 | 64% | 0.87 | -0.69 | REJECTED |
| NFLX | IBS | 270 | 64% | 1.17 | 0.86 | CONDITIONAL |
| NFLX | TOM | 132 | 61% | 1.79 | 4.22 | VALIDATED |
| MRK | RSI2 | 77 | 58% | 1.39 | 1.83 | CONDITIONAL |
| MRK | IBS | 233 | 55% | 0.92 | -0.48 | REJECTED |
| MRK | TOM | 132 | 62% | 1.27 | 2.07 | VALIDATED |
| LLY | RSI2 | 90 | 62% | 0.92 | -0.40 | REJECTED |
| LLY | IBS | 285 | 64% | 1.10 | 0.60 | CONDITIONAL |
| LLY | TOM | 132 | 59% | 1.51 | 2.81 | VALIDATED |
| PG | RSI2 | 79 | 65% | 1.31 | 1.50 | CONDITIONAL |
| PG | IBS | 235 | 57% | 0.79 | -1.29 | REJECTED |
| PG | TOM | 132 | 54% | 1.09 | 0.74 | CONDITIONAL |

---

## 4. Tier 3 — Single Strategy (PF > 1.3)

Assets VALIDATED sur **1 seule stratégie**.

| Asset | Strat | Trades | WR | PF | Sharpe | Robust | Verdict | Note |
|---|---|---:|---:|---:|---:|---:|---|---|
| COST | TOM | 132 | 58% | 1.66 | 3.58 | 100% | VALIDATED | Consumer defensive fort sur TOM |
| TSLA | TOM | 132 | 52% | 1.53 | 3.12 | 100% | VALIDATED | RSI2/IBS trop volatil |
| DIS | RSI2 | 66 | 65% | 1.55 | 2.58 | 83% | VALIDATED | IBS/TOM insuffisants |
| ABBV | TOM | 132 | 55% | 1.33 | 2.05 | 100% | VALIDATED | Pharma/biotech — effet TOM |
| WMT | TOM | 132 | 55% | 1.40 | 2.04 | 100% | VALIDATED | Défensif — TOM régulier |
| GS | TOM | 132 | 59% | 1.33 | 1.96 | 100% | VALIDATED | RSI2 rejeté (robust 50%), IBS négatif |
| HD | TOM | 132 | 54% | 1.36 | 2.22 | 100% | VALIDATED | Consumer cyclical |
| JPM | TOM | 132 | 56% | 1.30 | 1.94 | 100% | VALIDATED | Financier — effet TOM |
| CSCO | IBS | 217 | 67% | 1.37 | 1.79 | 100% | VALIDATED | RSI2 horrible (PF 0.57), TOM plat |

---

## 5. Rejected — Assets à ne pas trader

Assets rejetés sur les 3 stratégies ou avec PF < 1.0 dominant.

| Asset | RSI2 PF | IBS PF | TOM PF | Raison principale |
|---|---:|---:|---:|---|
| TSLA (IBS) | — | 0.86 | — | Trop volatile, IBS/RSI2 négatifs |
| NFLX (RSI2) | 0.87 | — | — | RSI2 négatif, momentum pur |
| BAC | 0.76 | 0.89 | 1.14 | Bancaire trop cyclique |
| JPM (RSI2/IBS) | 0.92 | 1.01 | — | Edge faible sauf TOM |
| GS (RSI2/IBS) | 1.55¹ | 0.75 | — | ¹RSI2 rejeté : robust 50% seulement |
| INTC | 0.86 | 1.02 | 1.07 | Déclin structurel, PF < 1.1 partout |
| CSCO (RSI2/TOM) | 0.57 | — | 1.06 | RSI2 très négatif |
| PFE / JNJ | <0.70 | <0.90 | ~1.12 | Pharma défensive — MR sans edge |
| PEP / KO | ~0.50 | ~1.00 | ~1.08 | Consumer staples — aucun edge |
| BA / UPS / CAT | <0.85 | <0.75 | <1.20 | Industriels cycliques, corrélés macro |
| XOM / CVX | <0.95 | <1.05 | <1.20 | Énergie — corrélé commodities |
| UBER / ABNB | <1.00 | <0.80 | <0.95 | Trop récents (IPO 2019/2020), edge insuffisant |
| SQ | — | — | — | Delisted (renommé XYZ) |

---

## 6. ETFs — Broad Market ($100k, fractional)

| ETF | RSI2 | PF | IBS | PF | TOM | PF | Score | Note |
|---|:---:|---:|:---:|---:|:---:|---:|:---:|---|
| **QQQ** | V | 1.85 | V | 1.45 | V | 1.47 | ★★★ | Meilleur ETF, 3 stratégies |
| **SPY** | R | 1.23 | C | 1.21 | V | 1.52 | ★★☆ | TOM fort, RSI2/IBS marginaux |
| **VOO** | R | 1.29 | V | 1.29 | V | 1.51 | ★★☆ | Quasi-identique à SPY¹ |
| **IVV** | R | 1.20 | V | 1.26 | V | 1.52 | ★★☆ | Quasi-identique à SPY¹ |
| **DIA** | V | 1.56 | R | 0.95 | V | 1.42 | ★★☆ | RSI2+TOM valides, IBS non |
| **VTI** | C | 1.22 | R | 1.15 | V | 1.43 | ★☆☆ | TOM seul solide |
| **MDY** | C | 1.31 | C | 1.07 | C | 1.25 | ★☆☆ | Tous CONDITIONAL — mid-cap |
| **IJR** | V | 1.77 | C | 1.12 | C | 1.14 | ★☆☆ | RSI2 fort, petites cap irrégulières |
| **IWM** | C | 1.10 | R | 0.99 | R | 1.06 | ☆☆☆ | Small cap — edge très faible |
| **EFA** | R | 0.99 | C | 1.41 | R | 0.95 | ☆☆☆ | Ex-US — instable |

**T-tests poolés :**
- RSI2 : 843 trades, t=3.02, p=0.0013
- IBS : 2553 trades, t=2.82, p=0.0024
- TOM : 1320 trades, t=3.91, p<0.0001

¹ SPY, VOO, IVV trackent le même indice (S&P 500) → trader **un seul** parmi les trois. Préférer SPY (liquidité maximale).

**Portefeuille ETF recommandé :** QQQ (3 stratégies), SPY ou QQQ TOM (effet fort), DIA RSI2. Éviter IWM et EFA.

---

## 7. ETFs — Sector ($100k, fractional)

| Secteur | ETF | RSI2 | PF | IBS | PF | TOM | PF | Score |
|---|---|:---:|---:|:---:|---:|:---:|---:|:---:|
| Comm. Services | XLC | R¹ | 2.65 | R¹ | 1.77 | V | 1.91 | ★★☆ |
| Technology | XLK | C | 1.42 | V | 1.72 | V | 1.37 | ★★★ |
| Consumer Discret. | XLY | V | 1.63 | R | 1.07 | V | 1.44 | ★★☆ |
| Industrials | XLI | C | 1.36 | R | 1.05 | V | 1.36 | ★★☆ |
| Healthcare | XLV | C | 1.22 | R | 1.08 | V | 1.39 | ★★☆ |
| Financials | XLF | C | 1.35 | R | 1.01 | V | 1.34 | ★★☆ |
| Materials | XLB | R | 1.12 | R | 1.03 | V | 1.36 | ★☆☆ |
| Energy | XLE | R | 0.98 | C | 1.10 | C | 1.12 | ☆☆☆ |
| Consumer Staples | XLP | R | 0.86 | R | 1.00 | C | 1.25 | ☆☆☆ |
| Utilities | XLU | R | 0.76 | R | 1.12 | C | 1.15 | ☆☆☆ |
| Real Estate | XLRE | R | 0.70 | R | 0.88 | V | 1.52 | ★☆☆ |

**T-tests poolés :**
- RSI2 : 823 trades, t=1.73, p=0.0416 (marginal)
- IBS : 2641 trades, t=2.32, p=0.0101
- TOM : 1374 trades, t=4.64, p<0.0001

¹ XLC RSI2/IBS REJECTED malgré PF élevé car robustesse <70% (seulement ~47 et 77 trades OOS — XLC lancé 2018, trop peu de recul).

**Observations :**
- **TOM domine les sectors :** 8/11 VALIDATED, 3/11 CONDITIONAL, 0 REJECTED. Effet fin-de-mois universel sur les secteurs.
- **RSI2 seulement viable sur XLY** (consumer discretionary) — secteur avec la meilleure mean reversion.
- **IBS seulement viable sur XLK** (tech) — seul secteur avec assez de volatilité intraday structurée.
- **Éviter :** XLE, XLP, XLU, XLRE pour RSI2/IBS. Ces secteurs sont dominés par le macro (pétrole, taux), pas par la mean reversion.

---

## 8. Forex — IBS ($100k, fractional)

> ⚠️ **AVERTISSEMENT AVANT TRADING LIVE** : Les résultats forex IBS sont exceptionnels statistiquement (t=12.61) mais présentent un pattern inhabituel (WR 37-48%) pour une stratégie mean reversion. Un WR <50% avec PF >2.5 indique une asymétrie gains/pertes importante — gains rares mais larges, pertes fréquentes mais petites. Ce comportement ressemble plus à du momentum que du mean reversion pur sur forex. À investiguer avant tout trading live.

| Paire | Trades | WR | PF | Sharpe | Net% OOS | Robust | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| **USDJPY=X** | 324 | 41% | 3.80 | 5.51 | +12.2% | 100% | VALIDATED |
| **AUDUSD=X** | 155 | 43% | 3.34 | 5.81 | +8.4% | 100% | VALIDATED |
| **GBPUSD=X** | 205 | 41% | 3.06 | 5.35 | +7.2% | 100% | VALIDATED |
| **USDCAD=X** | 288 | 44% | 3.03 | 5.33 | +10.9% | 100% | VALIDATED |
| **USDCHF=X** | 216 | 44% | 2.99 | 5.00 | +8.3% | 100% | VALIDATED |
| **EURUSD=X** | 192 | 37% | 2.55 | 4.47 | +5.6% | 100% | VALIDATED |
| **NZDUSD=X** | 201 | 48% | 2.51 | 4.34 | +9.0% | 100% | VALIDATED |

**T-test poolé :** 1581 trades, t=12.61, p<10⁻³⁴

**Points d'attention spécifiques forex :**
- IBS = (Close - Low) / (High - Low). Sur forex, les sessions (Londres, NY, Tokyo) créent des patterns H/L/C très différents des stocks.
- L'entry IBS < 0.2 + SMA200 sur forex capte peut-être les sessions où le cours clôture proche des plus bas — ce qui sur des paires trendy (USDJPY 2014-2022 : YEN bear market) peut indiquer continuation, pas mean reversion.
- Les Sharpe de 4-6 sont très élevés. Sur stocks, le meilleur est META RSI2 à 6.86. Des Sharpe similaires sur 7 paires différentes suggèrent soit un edge très robuste, soit un biais dans la construction du test.
- **Prochaine étape obligatoire :** ~~analyser la distribution des trades~~ — **FAIT**, voir verdict ci-dessous.

#### Investigation Verdict: Momentum Disguised as Mean Reversion

> **Date :** 2026-03-02
> **Script :** `scripts/investigate_ibs_forex.py`

The exceptional PF (2.5-3.8) with low WR (37-48%) reveals a fundamentally different mechanism than stock IBS:

**Evidence :**

1. **Asymmetric returns** — Mean skew +1.02, W/L ratio 4.15x, negative median returns. Opposite of stock MR profile (NVDA: WR 72%, W/L ratio 0.82, skew -0.55).
2. **Distributed edge** — Top 20 trades = 17% of pooled profit. PF remains 1.68-2.84 even without top 10 trades. Not an outlier artifact.
3. **Duration-return correlation** — r=0.25-0.41 (p<0.001). Longer trades (4-7d) return 2-3x more. Trades capture trend continuation, not quick bounces.
4. **Temporal stability** — 92% of pair-years have PF > 1.0 (68/74). USDCAD: 0 negative years over 11 years.
5. **No SMA200 slope dependency** — Near-zero correlation. Edge works in flat and rising trends equally.
6. **Exit mechanism is key** — `prev_high_exit` (close > yesterday's high) yields PF 6-17x. This acts as a trailing exit that lets winners run in trend direction. `ibs_exit` alone has PF 1.5-2.7.

**Mechanism :** On forex, IBS < 0.2 selects pullback days within a trend. The subsequent bounce is trend continuation, not mean reversion. The `close > high[j-1]` exit allows multi-day trend capture. On stocks, the same signal produces classic MR (frequent small wins).

**Decision : DEFERRED TO PHASE 4**

The edge is real and stable, but not suitable for immediate deployment:
- Requires separate forex setup (Saxo CFDs, different sizing, swap costs)
- Swap overnight costs not modeled (holding mean 1.5-2 days)
- Momentum mechanism = regime change risk if forex becomes range-bound
- Current focus: validate stock strategies with $5,000 capital first

When capital grows and stock workflow is proven, revisit forex IBS with:
- Swap cost modeling (Saxo rates)
- Regime detection (range-bound vs trending)
- Conservative position sizing (momentum = fatter tail risk)

---

## 9. Détails par stratégie

### RSI(2) Mean Reversion

**Paramètres canoniques :**
- Entry : RSI(2) < 10, close > SMA(200) × 1.01 (buffer 1%)
- Exit : close > SMA(5)
- Position : 20% du capital, long only, whole shares
- Fee model : $1 + 0.05% spread (USD account Saxo)

**Profil :**
- Trades typiques : 60-100 par asset sur 11 ans (5-9/an)
- WR typique : 65-75% sur les assets validés
- Durée trade moyenne : ~4 jours
- Fonctionne mieux sur : tech mega-cap croissance (META, V, MA, GOOGL) — forte tendance haussière + volatilité intraday
- Fonctionne mal sur : financières (GS, BAC, JPM), défensives (KO, PEP, JNJ), énergie, ETFs sectoriels
- Corrélation signaux : indépendant de IBS (signal différent, moins fréquent) ; partiellement anti-corrélé TOM (RSI2 capte les creux intraday, TOM les rotations calendaires)

**Risque principal :** AMZN et TSLA ont des PF >1.1 mais la robustesse paramétrique est insuffisante → ne pas trader RSI2 sur ces deux assets.

### IBS Mean Reversion

**Paramètres canoniques :**
- Entry : IBS = (Close-Low)/(High-Low) < 0.2, close > SMA(200)
- Exit : IBS > 0.8 **ou** close > High[j-1]
- Position : 100% allocation par signal¹, long only, whole shares
- Fee model : idem RSI2

**Profil :**
- Trades typiques : 200-320 par asset sur 11 ans (18-29/an) — 3-4× plus fréquent que RSI2
- WR typique : 60-70% sur les assets validés
- Durée trade moyenne : ~2-3 jours
- Fonctionne mieux sur : tech, growth, payment processors (V, MA) — volatilité intraday régulière
- Fonctionne mal sur : financières, pharma, consumer staples, énergie
- Corrélation signaux : IBS et RSI2 se chevauchent parfois (les deux signalent un creux), mais IBS est plus fréquent. En pratique, si les deux signalent en même temps, l'edge est additionnel.

¹ La fraction de position pour IBS dépend du capital total et du prix du stock — à $10k, le nombre d'actions entières limite l'exposition.

**Asset émergent :** CSCO IBS VALIDATED (PF 1.37, 100% robust) — surprenant car RSI2 est horrible (PF 0.57). Cisco est une action très "range-bound" qui réagit bien aux signaux IBS sans tendance forte.

### Turn of Month (TOM)

**Paramètres canoniques :**
- Entry : J derniers jours de trading du mois (default J=5)
- Exit : M-ème jour du nouveau mois (default M=3)
- Position : 100% allocation¹, long only
- Fee model : idem RSI2

**Profil :**
- Trades : **exactement 132** par asset sur 11 ans (12/an = 1 par mois)
- WR typique : 52-65% selon l'asset
- Durée trade : ~8 jours de trading (5 fins + 3 début)
- Fonctionne sur : **presque tout** — 21 VALIDATED sur 46 stocks, 8/11 sector ETFs, 6/10 broad ETFs
- Fonctionne moins bien sur : GOOGL (instable), MSFT (marginal), énergie/utilities/staples
- Corrélation signaux : **complètement décorrélé de RSI2 et IBS** — signal calendaire pur, pas technique. Un portefeuille RSI2+IBS+TOM est diversifié en type de signal.

¹ Position fraction TOM : 100% allocation means le capital entier est mobilisé 8 jours/mois. En pratique, avec $10k : 1 trade actif par mois, ~8 jours de holding.

**Points forts TOM :** Robustesse 100% sur pratiquement tous les assets validés (le signal calendaire est peu sensible aux paramètres). T-test poolé t=7.74 est le meilleur des 3 stratégies sur stocks.

---

## 10. Recommandations pour le trading live

### Portefeuille recommandé

**Priorité 1 — Core (Tier 1, 3 stratégies validées) :**

| Asset | Signaux actifs | Raison |
|---|---|---|
| META | RSI2 + IBS + TOM | Meilleur PF RSI2 (3.49), robuste sur 3 stratégies |
| V | RSI2 + IBS + TOM | WR RSI2 77% exceptionnel, 3 stratégies cohérentes |
| NVDA | RSI2 + IBS + TOM | IBS le plus fort (PF 2.07), TOM solide |
| MA | RSI2 + IBS + TOM | Profil très similaire à V¹ |
| AVGO | RSI2 + IBS + TOM | Le moins connu, PF > 1.4 sur les 3 |
| MSFT | RSI2 + IBS | TOM CONDITIONAL seulement — RSI2+IBS suffisants |
| AAPL | IBS + TOM | RSI2 CONDITIONAL — utiliser IBS+TOM par défaut |

¹ V et MA sont très corrélés (payment processors duopole). En cas de signal simultané, choisir l'un ou l'autre selon la position déjà ouverte.

**Priorité 2 — Extension (Tier 2, 2 stratégies) :**

| Asset | Signaux actifs | Raison |
|---|---|---|
| GOOGL | RSI2 + IBS | TOM REJECTED — uniquement les 2 MR |
| AMZN | IBS + TOM | RSI2 instable (robust 88%) — ne pas utiliser |
| ORCL | RSI2 + TOM | IBS PF 1.01 — sans edge |
| AMD | IBS + TOM | RSI2 instable — éviter |

**Priorité 3 — ETFs :**

| ETF | Signaux actifs | Capital |
|---|---|---|
| QQQ | RSI2 + IBS + TOM | $100k (fractional) |
| SPY ou IVV | TOM | $100k (1 seul parmi SPY/VOO/IVV) |
| DIA | RSI2 + TOM | $100k |

**Ne pas trader (yet) :** Forex IBS — investigation terminee (momentum deguise), deferred to Phase 4. Voir section 8.

### Sizing et capital

- **Stocks :** $10,000 par asset, whole shares, position_fraction=0.20 (RSI2) / variable (IBS/TOM)
- **ETFs :** $100,000 par ETF, fractional shares
- **Pas de levier**, long only
- **Contrainte prix :** AVGO (~$1,900) = 1 share par trade à $10k/20% = acceptable. NVDA (~$900) = 2 shares. Pas de problème sur META (~$550), V (~$280), MA (~$490).

### Risques identifiés

1. **Dégradation temporelle des edges MR :** Le RSI2 et l'IBS sont des effets bien documentés (Connors, Chan). La compétition algorithmique peut réduire ces edges. La robustesse paramétrique (100% sur la plupart des assets) atténue ce risque — les edges ne dépendent pas d'un paramètre exact.

2. **Corrélation entre assets :** META + NVDA + AMD sont corrélés (tech/semi). En cas de stress marché, plusieurs signaux IBS ou TOM peuvent se déclencher simultanément, concentrant le risque.

3. **Qualité des données Yahoo Finance :** Les prix sont ajustés pour splits et dividendes, mais des erreurs persistent sur certains assets (ex : ratios d'ajustement pour V et MA légèrement < 1 = signe de dividendes). Les résultats sur ces assets sont légèrement moins fiables.

4. **Sharpe attendu réaliste :** En live avec slippage réel > théorique (ouvertures gap, fills imparfaits) : réduire Sharpe de 20-30%. Un Sharpe backtest de 2.0 → ~1.5 en live.

5. **Paramètres canoniques non-optimisés :** Intentionnel. Utiliser les valeurs canoniques Connors pour RSI2, pas les valeurs optimisées. La robustesse 90-100% valide cette approche.

### Prochaines étapes

1. **Scanner quotidien** : `python scripts/daily_scanner.py` — actuellement RSI2 only sur META, MSFT, GOOGL, NVDA. Étendre aux signaux IBS et TOM pour les assets Tier 1.
2. **Dry run Saxo** : Paper trading sur META, V, NVDA pendant 2-3 mois. Vérifier la cohérence signaux vs executions.
3. **Live avec capital réduit** : Démarrer avec 1-2 assets (META + QQQ), valider le workflow complet avant d'élargir.
4. **Forex investigation** : ~~Analyser les 324 trades USDJPY IBS en detail~~ — **FAIT** (2026-03-02). Verdict : momentum deguise en MR, edge reel mais deferred to Phase 4 (swap costs, regime detection). Voir section 8.
5. **Mise à jour annuelle** : Relancer les validations complètes en janvier de chaque année pour vérifier que les edges persistent.

---

*Généré par signal-radar validation pipeline — `validation_results/full_validation_20260302_132726.txt`*
