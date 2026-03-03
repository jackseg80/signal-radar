# Analyse comparative : IBS + Turn of Month vs Turn of Month pur

Date : 2026-03-03
Periode OOS : 2014-01-01 a aujourd'hui
Capital : $10,000 (stocks whole shares), $100,000 (ETFs fractional)
Fee model : us_stocks_usd_account / us_etfs_usd_account

## Resume

Les resultats sont mitiges : le filtre IBS n'ameliore pas systematiquement le PF TOM. L'hypothese n'est pas confirmee sur cet univers.

## Hypothese testee

Les meilleurs trades TOM arrivent quand le marche est oversold en fin de mois (IBS < 0.2).
Le filtre IBS devrait eliminer les entrees sur des jours haussiers qui diluent l'edge.
Attendu : moins de trades, mais win rate et PF plus eleves.

**Params IBS+TOM :** entry_days_before_eom=5, ibs_entry_threshold=0.2, sma_trend_period=200,
exit_day_of_new_month=3, ibs_exit_threshold=0.8

## Synthese globale

| | Valeur |
|--|--|
| Assets analyses | 56 |
| Assets fiables (>= 20 trades IBS+TOM) | 55/56 |
| Winners (PF ameliore > +0.10) | 19 |
| Neutral | 11 |
| Losers (PF degrade > -0.10) | 26 |
| PF delta moyen (global) | +0.03 |
| Reduction trades moyenne | 50.9% |

## Resultats : us_stocks_large

### Vue d'ensemble

| Metrique | TOM pur | IBS+TOM | Delta |
|----------|---------|---------|-------|
| Trades (total) | 6545 | 3080 | -52.94% |
| PF (pond. trades) | 1.21 | 1.27 | +0.06 |
| WR (pond. trades) | 0.5% | 0.6% | +0.01% |
| PF delta moyen | - | - | +0.06 |
| PF delta median | - | - | +0.00 |
| Sharpe delta moyen | - | - | -0.11 |

Assets analyses : 46 (communs aux deux strategies)
Assets fiables (>= 20 trades IBS+TOM) : 45/46
Reduction de trades moyenne : 52.9%

### Resultats par categorie

**Winners (PF delta > +0.10) (17 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| DIS | 146 | 1.08 | 61 | 2.44 | +1.35 | +0.18% | yes |
| UBER | 80 | 0.89 | 29 | 2.06 | +1.17 | +0.15% | yes |
| CSCO | 146 | 1.15 | 65 | 2.05 | +0.90 | +0.10% | yes |
| NKE | 146 | 0.97 | 61 | 1.75 | +0.78 | +0.05% | yes |
| ADBE | 146 | 1.06 | 71 | 1.69 | +0.63 | +0.05% | yes |
| XOM | 146 | 1.11 | 56 | 1.72 | +0.62 | +0.07% | yes |
| KO | 146 | 1.05 | 67 | 1.58 | +0.53 | +0.05% | yes |
| CVX | 146 | 0.97 | 57 | 1.45 | +0.48 | -0.01% | yes |
| SBUX | 146 | 0.83 | 66 | 1.21 | +0.38 | +0.07% | yes |
| AAPL | 146 | 1.30 | 74 | 1.63 | +0.34 | +0.03% | yes |
| MS | 146 | 1.12 | 74 | 1.45 | +0.33 | +0.07% | yes |
| NFLX | 146 | 1.51 | 81 | 1.81 | +0.30 | +0.06% | yes |
| UNH | 146 | 1.15 | 82 | 1.43 | +0.28 | +0.03% | yes |
| META | 146 | 1.57 | 86 | 1.82 | +0.25 | -0.05% | yes |
| GE | 146 | 1.13 | 55 | 1.38 | +0.25 | +0.10% | yes |
| MCD | 146 | 1.15 | 76 | 1.33 | +0.18 | +0.04% | yes |
| PYPL | 126 | 0.84 | 43 | 0.94 | +0.10 | -0.02% | yes |

**Neutral (|PF delta| <= 0.10) (9 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| INTC | 146 | 1.13 | 52 | 1.23 | +0.10 | -0.05% | yes |
| CRM | 146 | 0.97 | 61 | 1.03 | +0.06 | +0.04% | yes |
| BAC | 146 | 1.11 | 72 | 1.16 | +0.06 | -0.03% | yes |
| WMT | 146 | 1.83 | 66 | 1.87 | +0.04 | +0.01% | yes |
| ABBV | 146 | 1.43 | 65 | 1.44 | +0.01 | +0.01% | yes |
| GS | 146 | 1.33 | 64 | 1.33 | +0.00 | -0.03% | yes |
| MSFT | 146 | 1.09 | 85 | 1.06 | -0.03 | +0.01% | yes |
| JPM | 146 | 1.33 | 76 | 1.28 | -0.05 | +0.02% | yes |
| PG | 146 | 1.05 | 68 | 0.96 | -0.09 | -0.03% | yes |

**Losers (PF delta < -0.10) (20 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| AMD | 146 | 1.10 | 64 | 0.99 | -0.12 | +0.03% | yes |
| AVGO | 146 | 1.40 | 85 | 1.26 | -0.14 | -0.00% | yes |
| MA | 146 | 1.42 | 79 | 1.27 | -0.15 | -0.07% | yes |
| TSLA | 146 | 1.18 | 59 | 1.03 | -0.16 | -0.05% | yes |
| AMZN | 146 | 1.24 | 77 | 1.08 | -0.16 | +0.03% | yes |
| HD | 146 | 1.38 | 74 | 1.21 | -0.17 | -0.06% | yes |
| BA | 146 | 1.07 | 61 | 0.85 | -0.23 | -0.02% | yes |
| PEP | 146 | 1.11 | 79 | 0.88 | -0.23 | -0.01% | yes |
| V | 146 | 1.45 | 89 | 1.15 | -0.30 | -0.03% | yes |
| PFE | 146 | 1.20 | 54 | 0.88 | -0.32 | -0.05% | yes |
| MRK | 146 | 1.31 | 66 | 0.97 | -0.34 | -0.05% | yes |
| GOOGL | 146 | 1.28 | 77 | 0.93 | -0.34 | -0.01% | yes |
| CAT | 146 | 1.36 | 61 | 1.00 | -0.36 | -0.03% | yes |
| ABNB | 61 | 0.79 | 19 | 0.42 | -0.37 | -0.16% | no (*) |
| UPS | 146 | 0.92 | 49 | 0.54 | -0.38 | -0.02% | yes |
| ORCL | 146 | 1.18 | 78 | 0.78 | -0.40 | +0.02% | yes |
| NVDA | 146 | 1.24 | 84 | 0.82 | -0.42 | -0.08% | yes |
| COST | 146 | 1.79 | 71 | 1.34 | -0.45 | -0.10% | yes |
| LLY | 146 | 1.58 | 77 | 1.03 | -0.55 | -0.04% | yes |
| JNJ | 146 | 1.29 | 64 | 0.60 | -0.69 | -0.09% | yes |

## Resultats : us_etfs_broad

### Vue d'ensemble

| Metrique | TOM pur | IBS+TOM | Delta |
|----------|---------|---------|-------|
| Trades (total) | 1460 | 746 | -48.90% |
| PF (pond. trades) | 1.29 | 1.21 | -0.09 |
| WR (pond. trades) | 0.6% | 0.5% | -0.03% |
| PF delta moyen | - | - | -0.09 |
| PF delta median | - | - | -0.14 |
| Sharpe delta moyen | - | - | -0.19 |

Assets analyses : 10 (communs aux deux strategies)
Assets fiables (>= 20 trades IBS+TOM) : 10/10
Reduction de trades moyenne : 48.9%

### Resultats par categorie

**Winners (PF delta > +0.10) (2 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| IJR | 146 | 1.15 | 70 | 1.59 | +0.45 | +0.04% | yes |
| QQQ | 146 | 1.38 | 69 | 1.59 | +0.21 | -0.04% | yes |

**Neutral (|PF delta| <= 0.10) (2 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| DIA | 146 | 1.44 | 81 | 1.53 | +0.09 | -0.01% | yes |
| IWM | 146 | 1.07 | 71 | 1.04 | -0.03 | +0.04% | yes |

**Losers (PF delta < -0.10) (6 assets)**

| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |
|-------|-----------|--------|----------------|------------|----------|----------|----------|
| VTI | 146 | 1.35 | 79 | 1.22 | -0.14 | -0.04% | yes |
| EFA | 146 | 1.03 | 62 | 0.81 | -0.22 | +0.02% | yes |
| MDY | 146 | 1.23 | 75 | 0.99 | -0.24 | -0.03% | yes |
| IVV | 146 | 1.43 | 79 | 1.11 | -0.32 | -0.08% | yes |
| VOO | 146 | 1.42 | 82 | 1.08 | -0.34 | -0.11% | yes |
| SPY | 146 | 1.42 | 78 | 1.07 | -0.35 | -0.09% | yes |

## Analyse

### 1. Le filtre IBS ameliore-t-il le PF ?

PF delta moyen global : +0.03.
Winners : 19, Losers : 26, Neutral : 11.

### 2. Le gain compense-t-il la perte de trades ?

Reduction moyenne de trades : 50.9%.
Assets avec >= 20 trades IBS+TOM : 55/56.
Un asset avec < 20 trades OOS n'est pas statistiquement exploitable.

### 3. Le filtre est-il trop restrictif ?

IBS < 0.2 filtre ~80% des entrees TOM. Si trade_reduction > 60%, la plupart des assets
passent sous le seuil de fiabilite statistique.

## Conclusion

Les resultats sont mitiges : le filtre IBS n'ameliore pas systematiquement le PF TOM. L'hypothese n'est pas confirmee sur cet univers.

## Recommandation

Garder ibs_tom en recherche sans l'ajouter au scanner. Explorer d'autres filtres d'entree (ex: RSI2 < 20 en fin de mois).
